"""Wallet, referrals and scratch cards (Phase 4).

Three rules shape this schema:

* **The ledger is the truth.** ``wallet_entries`` is append-only; the balance on
  ``wallets`` is a fast read that must always equal the sum of the entries. Every
  credit that could arrive twice (a referral, a card, a refund) stores the id of
  the entry it created in a unique column, so the database itself refuses the
  second one.
* **A card's value is decided by the server.** ``amount_paise`` is written when the
  card is created and simply not shown until it is revealed — a client cannot ask
  for ₹100.
* **Money never sits in a floating column.** Every amount is integer paise.
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
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import ReferralStatus, ScratchCardStatus, WalletReason


def _wallet_reason_enum() -> SAEnum:
    return SAEnum(
        WalletReason, name="wallet_reason", values_callable=lambda e: [m.value for m in e]
    )


def _referral_status_enum() -> SAEnum:
    return SAEnum(
        ReferralStatus, name="referral_status", values_callable=lambda e: [m.value for m in e]
    )


def _scratch_status_enum() -> SAEnum:
    return SAEnum(
        ScratchCardStatus,
        name="scratch_card_status",
        values_callable=lambda e: [m.value for m in e],
    )


class Wallet(Base, TimestampMixin):
    """One wallet per customer; the owner has none (the shop does not hold cash here)."""

    __tablename__ = "wallets"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("profiles.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    balance_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))

    entries: Mapped[list[WalletEntry]] = relationship(
        back_populates="wallet", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (CheckConstraint("balance_paise >= 0", name="balance_non_negative"),)


class WalletEntry(Base, TimestampMixin):
    """Append-only. ``balance_after_paise`` lets a statement be read without summing."""

    __tablename__ = "wallet_entries"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    wallet_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("wallets.id", ondelete="CASCADE"),
        nullable=False,
    )
    delta_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    balance_after_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reason: Mapped[WalletReason] = mapped_column(_wallet_reason_enum(), nullable=False)
    order_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    return_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("order_returns.id", ondelete="SET NULL"), nullable=True
    )
    scratch_card_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("scratch_cards.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    wallet: Mapped[Wallet] = relationship(back_populates="entries")

    __table_args__ = (
        CheckConstraint("delta_paise <> 0", name="delta_not_zero"),
        CheckConstraint("balance_after_paise >= 0", name="balance_after_non_negative"),
        Index("ix_wallet_entries_wallet_created", "wallet_id", "created_at"),
    )


class Referral(Base, TimestampMixin):
    """The link between a referrer and the friend they brought.

    ``referee_id`` is unique: a customer can be referred once, by one person, and
    the database enforces it rather than a service-level check racing itself.
    """

    __tablename__ = "referrals"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    referrer_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    referee_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(12), nullable=False)
    status: Mapped[ReferralStatus] = mapped_column(
        _referral_status_enum(), nullable=False, server_default=text("'pending'::referral_status")
    )
    #: What the friend actually got off their first order.
    discount_paise: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    #: What the referrer is promised, snapshotted from store settings at join time.
    reward_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    credited_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("wallet_entries.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    first_order_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True
    )
    credited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("referee_id", name="uq_referrals_referee"),
        CheckConstraint("referrer_id <> referee_id", name="no_self_referral"),
        CheckConstraint("reward_paise >= 0", name="reward_non_negative"),
        CheckConstraint("discount_paise >= 0", name="discount_non_negative"),
        Index("ix_referrals_referrer_status", "referrer_id", "status"),
    )


class ScratchCard(Base, TimestampMixin):
    """A card earned by a big order, unlocked when that order is delivered.

    ``status`` walks ``locked → ready → revealed``; ``void`` is for a card whose
    order came back or whose window closed before anyone rubbed it off.
    """

    __tablename__ = "scratch_cards"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[ScratchCardStatus] = mapped_column(
        _scratch_status_enum(),
        nullable=False,
        server_default=text("'locked'::scratch_card_status"),
    )
    #: The order's subtotal that earned it, for the "you spent ₹X" copy.
    threshold_paise: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    unlocked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revealed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    credited_entry_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("wallet_entries.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    void_reason: Mapped[str] = mapped_column(String(80), nullable=False, server_default="")
    #: How many times the customer peeked. A reveal is final; this is only for support.
    reveal_attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    __table_args__ = (
        UniqueConstraint("order_id", name="uq_scratch_cards_order"),
        CheckConstraint("amount_paise >= 0", name="amount_non_negative"),
        Index("ix_scratch_cards_profile_status", "profile_id", "status"),
    )
