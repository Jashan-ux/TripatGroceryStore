"""Store operations: the audit trail, offers and the feedback inbox (Phase 5).

Three tables, one owner (the merchant), and one rule that shaped all of them:
**the shop must be able to see what it did.** An offer cannot be sent without a
row recording who sent it and to how many people; a settings change cannot happen
without the before/after being written down; a customer's message cannot vanish
into an email inbox that the shop never checks.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin
from app.models.enums import FeedbackKind, FeedbackStatus, OfferAudience


def _audience_enum() -> SAEnum:
    return SAEnum(
        OfferAudience, name="offer_audience", values_callable=lambda e: [m.value for m in e]
    )


def _feedback_kind_enum() -> SAEnum:
    return SAEnum(
        FeedbackKind, name="feedback_kind", values_callable=lambda e: [m.value for m in e]
    )


def _feedback_status_enum() -> SAEnum:
    return SAEnum(
        FeedbackStatus, name="feedback_status", values_callable=lambda e: [m.value for m in e]
    )


class AuditLog(Base):
    """Append-only record of every owner action that changes the store.

    ``before``/``after`` hold only the fields that moved, so a row can be read as
    a sentence: "price_paise 32000 → 34000". There is no ``updated_at`` and no
    update path — an audit row that can be edited is not an audit row.
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_log_created", "created_at"),
        Index("ix_audit_log_entity", "entity", "entity_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    #: ``SET NULL``: removing a profile must not delete the history of what it did.
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    #: Copied at write time, so the row still reads correctly years later.
    actor_email: Mapped[str] = mapped_column(String(320), nullable=False, server_default="")
    #: Dotted verb: ``product.created``, ``settings.updated``, ``offer.sent``.
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    #: Coarse noun the action touched: ``product``, ``category``, ``brand``,
    #: ``settings``, ``offer``, ``feedback``.
    entity: Mapped[str] = mapped_column(String(40), nullable=False, server_default="")
    entity_id: Mapped[uuid.UUID | None] = mapped_column(PGUUID(as_uuid=True), nullable=True)
    #: A short human label of the row (product name, offer title) for the log list.
    summary: Mapped[str] = mapped_column(String(200), nullable=False, server_default="")
    before: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    after: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class Offer(Base, TimestampMixin):
    """One message the shop composed, plus how far it went."""

    __tablename__ = "offers"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    title: Mapped[str] = mapped_column(String(140), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    #: Where a tap should land. Empty means the home page.
    href: Mapped[str] = mapped_column(Text, nullable=False, server_default="/")
    audience: Mapped[OfferAudience] = mapped_column(_audience_enum(), nullable=False)
    #: The banner shows the newest live offer; this is how one is retired early.
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sent_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    recipients: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    emails_queued: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    #: Number of subscribed browser endpoints targeted at send time (not delivery receipts).
    push_queued: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_offers_created", "created_at"),
        CheckConstraint("recipients >= 0", name="recipients_non_negative"),
        CheckConstraint("push_queued >= 0", name="push_queued_non_negative"),
        CheckConstraint("char_length(title) > 0", name="title_not_empty"),
    )


class Feedback(Base, TimestampMixin):
    """A message from a customer, kept where the shop will actually see it."""

    __tablename__ = "feedback"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    #: Signed-in senders are linked; a guest message is still accepted.
    profile_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, server_default="")
    phone: Mapped[str] = mapped_column(String(20), nullable=False, server_default="")
    email: Mapped[str] = mapped_column(String(320), nullable=False, server_default="")
    kind: Mapped[FeedbackKind] = mapped_column(
        _feedback_kind_enum(), nullable=False, server_default=text("'general'::feedback_kind")
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[FeedbackStatus] = mapped_column(
        _feedback_status_enum(), nullable=False, server_default=text("'new'::feedback_status")
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_by: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("profiles.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        Index("ix_feedback_status_created", "status", "created_at"),
        CheckConstraint("char_length(message) > 0", name="message_not_empty"),
    )


__all__ = ["AuditLog", "Feedback", "Offer"]
