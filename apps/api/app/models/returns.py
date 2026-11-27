"""Returns (Phase 4).

A return is a small workflow with money at the end of it, so the state is explicit
and the credit happens exactly once:

    requested → approved → received_credited
              ↘ rejected

Only ``received_credited`` pays: the goods have to be back in the shop before the
wallet is topped up (C-16). ``credited_entry_id`` is unique, so a second "mark
received" — a double tap, a retried request — cannot pay twice (A-12).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ReturnStatus


def _return_status_enum() -> SAEnum:
    return SAEnum(
        ReturnStatus, name="return_status", values_callable=lambda e: [m.value for m in e]
    )


class OrderReturn(Base, TimestampMixin):
    __tablename__ = "order_returns"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[ReturnStatus] = mapped_column(
        _return_status_enum(), nullable=False, server_default=text("'requested'::return_status")
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    #: Sum of the chosen lines, capped at what the customer actually paid for them.
    refund_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    decision_note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    credited_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("wallet_entries.id", ondelete="SET NULL", use_alter=True),
        nullable=True,
        unique=True,
    )

    items: Mapped[list[ReturnItem]] = relationship(
        back_populates="order_return", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        CheckConstraint("refund_paise >= 0", name="refund_non_negative"),
        Index("ix_order_returns_profile_created", "profile_id", "created_at"),
        Index("ix_order_returns_status_created", "status", "created_at"),
    )


class ReturnItem(Base, TimestampMixin):
    """One line of a return, snapshotting the money so a later price edit cannot move it."""

    __tablename__ = "return_items"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    return_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("order_returns.id", ondelete="CASCADE"), nullable=False
    )
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False, server_default="")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    refund_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))

    order_return: Mapped[OrderReturn] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("refund_paise >= 0", name="refund_non_negative"),
        UniqueConstraint("return_id", "order_item_id", name="uq_return_items_line"),
    )
