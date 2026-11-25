"""Addresses, orders, order lines and order events.

Phase 2 schema. Notes that matter later:

* The order status enums are created here **idempotently**. They exist on the
  hosted project already (applied out of band in phase 0), and a fresh database
  needs them, so both paths land on the same schema.
* Orders snapshot the address and every line's name/price. Editing a product or
  deleting an address later must not rewrite what a customer was promised, so
  the FKs are ``RESTRICT`` on products and the receipt never joins back.
* ``uq_orders_profile_idempotency`` makes a retried checkout return the original
  order instead of charging twice.
* ``ck_orders_total_adds_up`` and ``ck_order_items_line_total_multiplies`` keep
  arithmetic errors out of the ledger entirely.

Revision ID: 0003_orders_and_addresses
Revises: 0002_profiles_and_catalogue
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_orders_and_addresses"
down_revision: str | None = "0002_profiles_and_catalogue"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'order_status') THEN
                CREATE TYPE order_status AS ENUM (
                    'processing', 'shipped', 'out_for_delivery',
                    'delivered', 'cancelled', 'returned'
                );
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_method') THEN
                CREATE TYPE payment_method AS ENUM ('cod');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'payment_status') THEN
                CREATE TYPE payment_status AS ENUM ('pending', 'paid');
            END IF;
        END $$;
        """
    )

    order_status = postgresql.ENUM(
        "processing",
        "shipped",
        "out_for_delivery",
        "delivered",
        "cancelled",
        "returned",
        name="order_status",
        create_type=False,
    )
    payment_method = postgresql.ENUM("cod", name="payment_method", create_type=False)
    payment_status = postgresql.ENUM("pending", "paid", name="payment_status", create_type=False)

    op.create_table(
        "addresses",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(40), nullable=False, server_default="Home"),
        sa.Column("recipient_name", sa.String(120), nullable=False),
        sa.Column("phone", sa.String(20), nullable=False),
        sa.Column("line1", sa.Text(), nullable=False),
        sa.Column("line2", sa.Text(), nullable=False, server_default=""),
        sa.Column("landmark", sa.String(120), nullable=False, server_default=""),
        sa.Column("pincode", sa.String(6), nullable=False),
        sa.Column("city", sa.String(80), nullable=False, server_default=""),
        sa.Column("state", sa.String(80), nullable=False, server_default=""),
        sa.Column("latitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("longitude", sa.Numeric(9, 6), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("pincode ~ '^[0-9]{6}$'", name="ck_addresses_pincode_six_digits"),
    )
    op.create_index("ix_addresses_profile", "addresses", ["profile_id"])

    op.create_table(
        "orders",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("order_number", sa.String(24), nullable=False),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("status", order_status, nullable=False, server_default=sa.text("'processing'")),
        sa.Column("payment_method", payment_method, nullable=False, server_default=sa.text("'cod'")),
        sa.Column(
            "payment_status", payment_status, nullable=False, server_default=sa.text("'pending'")
        ),
        sa.Column("subtotal_paise", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("delivery_fee_paise", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("discount_paise", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_paise", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("item_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("customer_name", sa.String(120), nullable=False, server_default=""),
        sa.Column("customer_phone", sa.String(20), nullable=False, server_default=""),
        sa.Column(
            "address_snapshot",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("delivery_days", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("deliver_by", sa.Date(), nullable=True),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("customer_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.UniqueConstraint("order_number", name="uq_orders_order_number"),
        sa.UniqueConstraint("profile_id", "idempotency_key", name="uq_orders_profile_idempotency"),
        sa.CheckConstraint("subtotal_paise >= 0", name="ck_orders_subtotal_non_negative"),
        sa.CheckConstraint("delivery_fee_paise >= 0", name="ck_orders_delivery_fee_non_negative"),
        sa.CheckConstraint("discount_paise >= 0", name="ck_orders_discount_non_negative"),
        sa.CheckConstraint("total_paise >= 0", name="ck_orders_total_non_negative"),
        sa.CheckConstraint("item_count > 0", name="ck_orders_item_count_positive"),
        sa.CheckConstraint(
            "total_paise = subtotal_paise + delivery_fee_paise - discount_paise",
            name="ck_orders_total_adds_up",
        ),
    )
    op.create_index("ix_orders_profile_placed", "orders", ["profile_id", "placed_at"])
    op.create_index("ix_orders_status_placed", "orders", ["status", "placed_at"])

    op.create_table(
        "order_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "variant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("product_variants.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("unit_label", sa.String(40), nullable=False, server_default=""),
        sa.Column("variant_label", sa.String(40), nullable=False, server_default=""),
        sa.Column("image_url", sa.Text(), nullable=False, server_default=""),
        sa.Column("unit_price_paise", sa.BigInteger(), nullable=False),
        sa.Column("mrp_paise", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("line_total_paise", sa.BigInteger(), nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.CheckConstraint("quantity > 0", name="ck_order_items_quantity_positive"),
        sa.CheckConstraint(
            "unit_price_paise >= 0", name="ck_order_items_unit_price_non_negative"
        ),
        sa.CheckConstraint(
            "line_total_paise = unit_price_paise * quantity",
            name="ck_order_items_line_total_multiplies",
        ),
    )
    op.create_index("ix_order_items_order", "order_items", ["order_id"])

    op.create_table(
        "order_events",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", order_status, nullable=False),
        sa.Column("actor", sa.String(16), nullable=False, server_default="system"),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("ix_order_events_order_created", "order_events", ["order_id", "created_at"])

    for table in ("addresses", "orders"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON public.{table}")
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_updated_at
                BEFORE UPDATE ON public.{table}
                FOR EACH ROW EXECUTE FUNCTION set_updated_at()
            """
        )

    op.execute("SELECT app_harden_public_tables()")


def downgrade() -> None:
    for table in ("order_events", "order_items", "orders", "addresses"):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON public.{table}")
    op.drop_table("order_events")
    op.drop_table("order_items")
    op.drop_table("orders")
    op.drop_table("addresses")
    # The enums are left in place: they may predate this migration on a hosted
    # project, and dropping a type another table still uses fails loudly.
