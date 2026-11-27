"""Addresses, orders, order lines and the order event log (Phase 2).

Money is integer paise everywhere. Two rules shape the schema:

* An order keeps a **snapshot** of the address and of every line's name, unit and
  price. Catalogue edits and profile edits later must never rewrite what the
  customer was promised.
* Stock is decremented by a conditional ``UPDATE ... WHERE stock >= qty`` inside
  the order transaction, so two simultaneous orders for the last unit cannot both
  succeed.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.enums import OrderStatus, PaymentMethod, PaymentStatus


def _status_enum() -> SAEnum:
    return SAEnum(OrderStatus, name="order_status", values_callable=lambda e: [m.value for m in e])


def _payment_method_enum() -> SAEnum:
    return SAEnum(
        PaymentMethod, name="payment_method", values_callable=lambda e: [m.value for m in e]
    )


def _payment_status_enum() -> SAEnum:
    return SAEnum(
        PaymentStatus, name="payment_status", values_callable=lambda e: [m.value for m in e]
    )


class Address(Base, TimestampMixin):
    """A saved delivery address. Owned by exactly one profile."""

    __tablename__ = "addresses"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(40), nullable=False, server_default="Home")
    recipient_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    line1: Mapped[str] = mapped_column(Text, nullable=False)
    line2: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    landmark: Mapped[str] = mapped_column(String(120), nullable=False, server_default="")
    pincode: Mapped[str] = mapped_column(String(6), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False, server_default="")
    state: Mapped[str] = mapped_column(String(80), nullable=False, server_default="")
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    __table_args__ = (
        CheckConstraint("pincode ~ '^[0-9]{6}$'", name="pincode_six_digits"),
        Index("ix_addresses_profile", "profile_id"),
    )


class Order(Base, TimestampMixin):
    """A placed order. ``order_number`` is what the customer quotes on the phone."""

    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    order_number: Mapped[str] = mapped_column(String(24), nullable=False)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("profiles.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[OrderStatus] = mapped_column(
        # Declared in migration 0003 rather than inferred, so the type name and
        # values match the database exactly.
        _status_enum(),
        nullable=False,
        server_default=text("'processing'::order_status"),
    )
    payment_method: Mapped[PaymentMethod] = mapped_column(
        _payment_method_enum(), nullable=False, server_default=text("'cod'::payment_method")
    )
    payment_status: Mapped[PaymentStatus] = mapped_column(
        _payment_status_enum(), nullable=False, server_default=text("'pending'::payment_status")
    )

    subtotal_paise: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    delivery_fee_paise: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    discount_paise: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default=text("0")
    )
    #: Part of the order paid from the customer's wallet instead of cash.
    wallet_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    #: Why a discount was given ("Referral 10% off"), for the receipt.
    discount_reason: Mapped[str] = mapped_column(String(40), nullable=False, server_default="")
    total_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    item_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    # Snapshots: the order never joins back to mutable tables for the receipt.
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False, server_default="")
    customer_phone: Mapped[str] = mapped_column(String(20), nullable=False, server_default="")
    address_snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    delivery_days: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("1")
    )
    deliver_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    placed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_reason: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    customer_note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    #: Supplied by the client; a replay returns the original order instead of
    #: charging twice. Unique per customer, not globally.
    idempotency_key: Mapped[str | None] = mapped_column(String(64), nullable=True)

    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan", lazy="selectin"
    )
    events: Mapped[list[OrderEvent]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
        order_by="OrderEvent.created_at",
    )

    __table_args__ = (
        UniqueConstraint("order_number", name="uq_orders_order_number"),
        UniqueConstraint("profile_id", "idempotency_key", name="uq_orders_profile_idempotency"),
        CheckConstraint("subtotal_paise >= 0", name="subtotal_non_negative"),
        CheckConstraint("delivery_fee_paise >= 0", name="delivery_fee_non_negative"),
        CheckConstraint("discount_paise >= 0", name="discount_non_negative"),
        CheckConstraint("total_paise >= 0", name="total_non_negative"),
        CheckConstraint("item_count > 0", name="item_count_positive"),
        CheckConstraint(
            "total_paise = subtotal_paise + delivery_fee_paise - discount_paise - wallet_paise",
            name="total_adds_up",
        ),
        CheckConstraint("wallet_paise >= 0", name="wallet_non_negative"),
        CheckConstraint(
            "wallet_paise <= subtotal_paise + delivery_fee_paise - discount_paise",
            name="wallet_within_order",
        ),
        Index("ix_orders_profile_placed", "profile_id", "placed_at"),
        Index("ix_orders_status_placed", "status", "placed_at"),
        # Analytics (Phase 6) scans by date across all customers.
        Index("ix_orders_placed", "placed_at"),
    )


class OrderItem(Base):
    """One line of an order, snapshotted at placement."""

    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("product_variants.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    unit_label: Mapped[str] = mapped_column(String(40), nullable=False, server_default="")
    variant_label: Mapped[str] = mapped_column(String(40), nullable=False, server_default="")
    image_url: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    unit_price_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    mrp_paise: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default=text("0"))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    line_total_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default=text("0"))

    order: Mapped[Order] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        # "What actually sold": lines rolled up per product, joined back by order.
        Index("ix_order_items_product_order", "product_id", "order_id"),
        CheckConstraint("unit_price_paise >= 0", name="unit_price_non_negative"),
        CheckConstraint(
            "line_total_paise = unit_price_paise * quantity", name="line_total_multiplies"
        ),
        Index("ix_order_items_order", "order_id"),
    )


class OrderEvent(Base):
    """Append-only status history; the customer timeline reads exactly this."""

    __tablename__ = "order_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[OrderStatus] = mapped_column(_status_enum(), nullable=False)
    #: `customer` | `admin` | `system`
    actor: Mapped[str] = mapped_column(String(16), nullable=False, server_default="system")
    note: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    order: Mapped[Order] = relationship(back_populates="events")

    __table_args__ = (Index("ix_order_events_order_created", "order_id", "created_at"),)
