"""Wallet, referrals, scratch cards and returns.

Phase 4 schema. Three things worth knowing before reading:

* ``wallet_entries`` is append-only and ``wallets.balance_paise`` must always equal
  the sum of its entries. The credit paths that could fire twice (referral, card,
  refund) each store the id of the entry they made in a **unique** column, so the
  database refuses the second credit rather than trusting a service check.
* ``scratch_cards.amount_paise`` is written at creation and hidden by the API until
  it is revealed: the prize is decided by the server, never by the request.
* ``orders`` grows two columns — the part paid from the wallet and the reason for
  any discount — and its ``total_adds_up`` check is rewritten so the arithmetic
  stays enforced in the database: ``total = subtotal + fee − discount − wallet``.

Revision ID: 0005_wallet_referrals_rewards
Revises: 0004_notifications_and_email
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_wallet_referrals_rewards"
down_revision: str | None = "0004_notifications_and_email"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NEW_TABLES = ("wallets", "wallet_entries", "referrals", "scratch_cards")
RETURN_TABLES = ("order_returns", "return_items")


def upgrade() -> None:
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'wallet_reason') THEN
                CREATE TYPE wallet_reason AS ENUM (
                    'referral_bonus', 'scratch_card', 'return_refund',
                    'order_payment', 'adjustment'
                );
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'referral_status') THEN
                CREATE TYPE referral_status AS ENUM ('pending', 'credited', 'void');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'scratch_card_status') THEN
                CREATE TYPE scratch_card_status AS ENUM (
                    'locked', 'ready', 'revealed', 'used', 'void'
                );
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'return_status') THEN
                CREATE TYPE return_status AS ENUM (
                    'requested', 'approved', 'rejected', 'received_credited'
                );
            END IF;
        END $$;
        """
    )

    wallet_reason = postgresql.ENUM(name="wallet_reason", create_type=False)
    referral_status = postgresql.ENUM(name="referral_status", create_type=False)
    scratch_card_status = postgresql.ENUM(name="scratch_card_status", create_type=False)
    return_status = postgresql.ENUM(name="return_status", create_type=False)

    op.create_table(
        "wallets",
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
            unique=True,
        ),
        sa.Column("balance_paise", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_wallets"),
        sa.CheckConstraint("balance_paise >= 0", name="ck_wallets_balance_non_negative"),
    )

    op.create_table(
        "order_returns",
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
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            return_status,
            nullable=False,
            server_default=sa.text("'requested'::return_status"),
        ),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("refund_paise", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "requested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "decided_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("decision_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        # The foreign key to wallet_entries is added below: the ledger points at
        # returns too, so one of the two has to be wired up second.
        sa.Column("credited_entry_id", postgresql.UUID(as_uuid=True), nullable=True, unique=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_order_returns"),
        sa.CheckConstraint("refund_paise >= 0", name="ck_order_returns_refund_non_negative"),
    )
    op.create_index(
        "ix_order_returns_profile_created", "order_returns", ["profile_id", "created_at"]
    )
    op.create_index("ix_order_returns_status_created", "order_returns", ["status", "created_at"])

    op.create_table(
        "return_items",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "return_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("order_returns.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "order_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("order_items.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("refund_paise", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_return_items"),
        sa.UniqueConstraint("return_id", "order_item_id", name="uq_return_items_line"),
        sa.CheckConstraint("quantity > 0", name="ck_return_items_quantity_positive"),
        sa.CheckConstraint("refund_paise >= 0", name="ck_return_items_refund_non_negative"),
    )

    op.create_table(
        "scratch_cards",
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
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "status",
            scratch_card_status,
            nullable=False,
            server_default=sa.text("'locked'::scratch_card_status"),
        ),
        sa.Column("threshold_paise", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("amount_paise", sa.BigInteger(), nullable=False),
        sa.Column("unlocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revealed_at", sa.DateTime(timezone=True), nullable=True),
        # FK added after wallet_entries exists (see the note on order_returns).
        sa.Column("credited_entry_id", postgresql.UUID(as_uuid=True), nullable=True, unique=True),
        sa.Column("void_reason", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("reveal_attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_scratch_cards"),
        sa.UniqueConstraint("order_id", name="uq_scratch_cards_order"),
        sa.CheckConstraint("amount_paise >= 0", name="ck_scratch_cards_amount_non_negative"),
    )
    op.create_index("ix_scratch_cards_profile_status", "scratch_cards", ["profile_id", "status"])

    op.create_table(
        "wallet_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "wallet_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wallets.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("delta_paise", sa.BigInteger(), nullable=False),
        sa.Column("balance_after_paise", sa.BigInteger(), nullable=False),
        sa.Column("reason", wallet_reason, nullable=False),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "return_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("order_returns.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "scratch_card_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("scratch_cards.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_wallet_entries"),
        sa.CheckConstraint("delta_paise <> 0", name="ck_wallet_entries_delta_not_zero"),
        sa.CheckConstraint(
            "balance_after_paise >= 0", name="ck_wallet_entries_balance_after_non_negative"
        ),
    )
    op.create_index(
        "ix_wallet_entries_wallet_created", "wallet_entries", ["wallet_id", "created_at"]
    )

    op.create_table(
        "referrals",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "referrer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "referee_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=12), nullable=False),
        sa.Column(
            "status",
            referral_status,
            nullable=False,
            server_default=sa.text("'pending'::referral_status"),
        ),
        sa.Column("discount_paise", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("reward_paise", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "credited_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("wallet_entries.id", ondelete="SET NULL"),
            nullable=True,
            unique=True,
        ),
        sa.Column(
            "first_order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("credited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_referrals"),
        sa.UniqueConstraint("referee_id", name="uq_referrals_referee"),
        sa.CheckConstraint("referrer_id <> referee_id", name="ck_referrals_no_self_referral"),
        sa.CheckConstraint("reward_paise >= 0", name="ck_referrals_reward_non_negative"),
        sa.CheckConstraint("discount_paise >= 0", name="ck_referrals_discount_non_negative"),
    )
    op.create_index("ix_referrals_referrer_status", "referrals", ["referrer_id", "status"])

    # The two credits that point back at the ledger, wired up once it exists.
    for table in ("order_returns", "scratch_cards"):
        op.create_foreign_key(
            f"fk_{table}_credited_entry_id_wallet_entries",
            table,
            "wallet_entries",
            ["credited_entry_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # The order grows a wallet column and a reason for its discount, and the
    # arithmetic check is rewritten to include both.
    op.add_column(
        "orders",
        sa.Column("wallet_paise", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "orders",
        sa.Column("discount_reason", sa.String(length=40), nullable=False, server_default=""),
    )
    # 0003 declared this check *inside* `create_table`, so the naming convention
    # produced `ck_orders_ck_orders_total_adds_up`, while a later manual recreation
    # left `ck_orders_total_adds_up` on the hosted project. Drop whichever is there
    # and then name the replacement explicitly, so every database converges on the
    # same name.
    op.execute(
        """
        DO $$
        DECLARE
            found text;
        BEGIN
            FOR found IN
                SELECT conname FROM pg_constraint
                WHERE conrelid = 'orders'::regclass
                  AND contype = 'c'
                  AND conname IN ('ck_orders_total_adds_up', 'ck_orders_ck_orders_total_adds_up')
            LOOP
                EXECUTE format('ALTER TABLE orders DROP CONSTRAINT %I', found);
            END LOOP;
        END $$;
        """
    )
    op.execute(
        "ALTER TABLE orders ADD CONSTRAINT ck_orders_total_adds_up "
        "CHECK (total_paise = subtotal_paise + delivery_fee_paise "
        "- discount_paise - wallet_paise)"
    )
    op.execute(
        "ALTER TABLE orders ADD CONSTRAINT ck_orders_wallet_non_negative CHECK (wallet_paise >= 0)"
    )
    op.execute(
        "ALTER TABLE orders ADD CONSTRAINT ck_orders_wallet_within_order CHECK ("
        "wallet_paise <= subtotal_paise + delivery_fee_paise - discount_paise)"
    )

    # One statement per `op.execute`: asyncpg prepares each execute, and a
    # prepared statement cannot carry two commands (CI caught exactly that once).
    for table in (*NEW_TABLES, *RETURN_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON public.{table}")
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_updated_at
                BEFORE UPDATE ON public.{table}
                FOR EACH ROW EXECUTE FUNCTION set_updated_at()
            """
        )

    # RLS + revoked grants for the new tables (the baseline installs the guard).
    op.execute("SELECT app_harden_public_tables()")


def downgrade() -> None:
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")
    for table in (*NEW_TABLES, *RETURN_TABLES):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON public.{table}")

    # Explicit names, matching what `upgrade` created (see the note there).
    for name in (
        "ck_orders_wallet_within_order",
        "ck_orders_wallet_non_negative",
        "ck_orders_total_adds_up",
    ):
        op.execute(f"ALTER TABLE orders DROP CONSTRAINT IF EXISTS {name}")
    op.execute(
        "ALTER TABLE orders ADD CONSTRAINT ck_orders_total_adds_up "
        "CHECK (total_paise = subtotal_paise + delivery_fee_paise - discount_paise)"
    )
    op.drop_column("orders", "discount_reason")
    op.drop_column("orders", "wallet_paise")

    # Out with the referencing tables first: the ledger points at returns and
    # cards, and both of those point back at the ledger, so the two deferred
    # foreign keys come off before the middle table can go.
    op.drop_table("return_items")
    op.drop_index("ix_referrals_referrer_status", table_name="referrals")
    op.drop_table("referrals")
    for table in ("order_returns", "scratch_cards"):
        op.drop_constraint(
            f"fk_{table}_credited_entry_id_wallet_entries", table, type_="foreignkey"
        )
    op.drop_index("ix_wallet_entries_wallet_created", table_name="wallet_entries")
    op.drop_table("wallet_entries")
    op.drop_index("ix_scratch_cards_profile_status", table_name="scratch_cards")
    op.drop_table("scratch_cards")
    op.drop_index("ix_order_returns_status_created", table_name="order_returns")
    op.drop_index("ix_order_returns_profile_created", table_name="order_returns")
    op.drop_table("order_returns")
    op.drop_table("wallets")

    op.execute("DROP TYPE IF EXISTS return_status")
    op.execute("DROP TYPE IF EXISTS scratch_card_status")
    op.execute("DROP TYPE IF EXISTS referral_status")
    op.execute("DROP TYPE IF EXISTS wallet_reason")
