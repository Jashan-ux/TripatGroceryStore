"""Profiles, catalogue, variants and store settings.

Phase 1 schema. Notes that matter later:

* ``profiles.id`` is the Supabase auth user id; the FK to ``auth.users`` is added
  only when that table exists (Supabase yes, plain Postgres no), so the same
  migrations run in CI's Postgres service container.
* ``profiles.email`` and ``brands.name`` are unique case-insensitively via
  functional indexes — no citext dependency.
* ``products.search_text`` is maintained by a trigger, so search can never drift
  from the row it describes, whoever writes it.
* The trigram index uses ``gin_trgm_ops``; ``search_path`` includes
  ``extensions`` because that is where Supabase installs pg_trgm.
* ``store_settings`` gets its singleton row here (structural defaults only — no
  catalogue data, which belongs to the seed script).

Revision ID: 0002_profiles_and_catalogue
Revises: 0001_baseline
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_profiles_and_catalogue"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

NOW = sa.text("now()")


def upgrade() -> None:
    # pg_trgm may live in `extensions` (Supabase) or `public` (plain Postgres).
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")

    # --- enums ---------------------------------------------------------------
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
                CREATE TYPE user_role AS ENUM ('customer', 'admin', 'delivery');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'loyalty_tier') THEN
                CREATE TYPE loyalty_tier AS ENUM ('none', 'gold', 'platinum', 'diamond');
            END IF;
        END $$;
        """
    )

    # --- profiles ------------------------------------------------------------
    op.create_table(
        "profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, server_default=""),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column(
            "role",
            postgresql.ENUM("customer", "admin", "delivery", name="user_role", create_type=False),
            nullable=False,
            server_default=sa.text("'customer'::user_role"),
        ),
        sa.Column("referral_code", sa.String(12), nullable=False),
        sa.Column(
            "referred_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "lifetime_spend_paise", sa.BigInteger(), nullable=False, server_default=sa.text("0")
        ),
        sa.Column(
            "loyalty_tier",
            postgresql.ENUM(
                "none", "gold", "platinum", "diamond", name="loyalty_tier", create_type=False
            ),
            nullable=False,
            server_default=sa.text("'none'::loyalty_tier"),
        ),
        sa.Column(
            "notification_prefs",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint("lifetime_spend_paise >= 0", name="lifetime_spend_non_negative"),
    )
    op.execute("CREATE UNIQUE INDEX uq_profiles_email_lower ON public.profiles (lower(email))")
    op.create_index(
        "uq_profiles_phone",
        "profiles",
        ["phone"],
        unique=True,
        postgresql_where=sa.text("phone IS NOT NULL"),
    )
    op.create_index("uq_profiles_referral_code", "profiles", ["referral_code"], unique=True)
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM information_schema.tables
                       WHERE table_schema = 'auth' AND table_name = 'users') THEN
                ALTER TABLE public.profiles
                    ADD CONSTRAINT fk_profiles_auth_user
                    FOREIGN KEY (id) REFERENCES auth.users (id) ON DELETE CASCADE;
            END IF;
        END $$;
        """
    )

    # --- brands --------------------------------------------------------------
    op.create_table(
        "brands",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(140), nullable=False),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.UniqueConstraint("slug", name="uq_brands_slug"),
    )
    op.execute("CREATE UNIQUE INDEX uq_brands_name_lower ON public.brands (lower(name))")

    # --- categories ----------------------------------------------------------
    op.create_table(
        "categories",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("slug", sa.String(140), nullable=False),
        sa.Column("emoji", sa.String(16), nullable=True),
        sa.Column("image_url", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.UniqueConstraint("slug", name="uq_categories_slug"),
        sa.CheckConstraint("sort_order >= 0", name="sort_order_non_negative"),
        sa.CheckConstraint("parent_id IS NULL OR parent_id <> id", name="no_self_parent"),
    )
    op.create_index("ix_categories_parent_sort", "categories", ["parent_id", "sort_order"])

    # --- products ------------------------------------------------------------
    op.create_table(
        "products",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(220), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("brands.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "category_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("mrp_paise", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("price_paise", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("unit_label", sa.String(40), nullable=False, server_default=""),
        sa.Column("stock", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "low_stock_threshold", sa.Integer(), nullable=False, server_default=sa.text("10")
        ),
        sa.Column(
            "images",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "tags",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("rating", sa.Numeric(2, 1), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("search_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.UniqueConstraint("slug", name="uq_products_slug"),
        sa.CheckConstraint("price_paise >= 0", name="price_non_negative"),
        sa.CheckConstraint("mrp_paise >= 0", name="mrp_non_negative"),
        sa.CheckConstraint("stock >= 0", name="stock_non_negative"),
        sa.CheckConstraint("low_stock_threshold >= 0", name="low_stock_non_negative"),
        sa.CheckConstraint("rating >= 0 AND rating <= 5", name="rating_range"),
    )
    op.create_index("ix_products_category_active", "products", ["category_id", "is_active"])
    op.create_index("ix_products_brand", "products", ["brand_id"])
    op.create_index("ix_products_price", "products", ["price_paise"])
    op.execute(
        "CREATE INDEX ix_products_search_trgm ON public.products "
        "USING gin (search_text gin_trgm_ops)"
    )
    op.execute("CREATE INDEX ix_products_tags ON public.products USING gin (tags)")

    # --- product variants ----------------------------------------------------
    op.create_table(
        "product_variants",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(40), nullable=False),
        sa.Column("mrp_paise", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("price_paise", sa.BigInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("stock", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.UniqueConstraint("product_id", "label", name="uq_product_variants_product_label"),
        sa.CheckConstraint("price_paise >= 0", name="variant_price_non_negative"),
        sa.CheckConstraint("stock >= 0", name="variant_stock_non_negative"),
    )

    # --- store settings (singleton) -----------------------------------------
    op.create_table(
        "store_settings",
        sa.Column("id", sa.Integer(), primary_key=True, server_default=sa.text("1")),
        sa.Column(
            "store_name", sa.String(120), nullable=False, server_default="Tripat Pansari MSG Store"
        ),
        sa.Column("store_phone", sa.String(24), nullable=False, server_default="+91 87089-73386"),
        sa.Column(
            "store_address",
            sa.Text(),
            nullable=False,
            server_default=(
                "Tripat Pansari MSG Store, near Sabji Mandi, opposite Gyani Achhar Bhandaar, "
                "Mandi Dabwali, 125104"
            ),
        ),
        sa.Column("store_maps_url", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "feedback_email",
            sa.String(320),
            nullable=False,
            server_default="tripatinsan029@gmail.com",
        ),
        sa.Column(
            "minimum_order_paise", sa.BigInteger(), nullable=False, server_default=sa.text("50000")
        ),
        sa.Column(
            "serviceable_pincodes",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{125104,125201}'::text[]"),
        ),
        sa.Column(
            "default_delivery_days", sa.SmallInteger(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "low_stock_threshold", sa.Integer(), nullable=False, server_default=sa.text("10")
        ),
        sa.Column(
            "referral_referrer_reward_paise",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("2000"),
        ),
        sa.Column(
            "referral_friend_discount_pct",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("10"),
        ),
        sa.Column(
            "referral_credit_trigger", sa.String(16), nullable=False, server_default="delivered"
        ),
        sa.Column(
            "scratch_threshold_paise",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("200000"),
        ),
        sa.Column(
            "scratch_min_paise", sa.BigInteger(), nullable=False, server_default=sa.text("5000")
        ),
        sa.Column(
            "scratch_max_paise", sa.BigInteger(), nullable=False, server_default=sa.text("10000")
        ),
        sa.Column(
            "scratch_expiry_days", sa.SmallInteger(), nullable=False, server_default=sa.text("30")
        ),
        sa.Column(
            "return_window_days", sa.SmallInteger(), nullable=False, server_default=sa.text("3")
        ),
        sa.Column(
            "tier_gold_paise", sa.BigInteger(), nullable=False, server_default=sa.text("2000000")
        ),
        sa.Column(
            "tier_platinum_paise",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("5000000"),
        ),
        sa.Column(
            "tier_diamond_paise",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("10000000"),
        ),
        sa.Column("notification_email", sa.String(320), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=NOW),
        sa.CheckConstraint("id = 1", name="singleton"),
        sa.CheckConstraint("minimum_order_paise >= 0", name="minimum_order_non_negative"),
        sa.CheckConstraint("scratch_min_paise <= scratch_max_paise", name="scratch_range_ordered"),
        sa.CheckConstraint(
            "tier_gold_paise < tier_platinum_paise " "AND tier_platinum_paise < tier_diamond_paise",
            name="tiers_ordered",
        ),
        sa.CheckConstraint("default_delivery_days >= 0", name="delivery_days_non_negative"),
    )
    op.execute("INSERT INTO public.store_settings (id) VALUES (1) ON CONFLICT (id) DO NOTHING")

    # --- triggers ------------------------------------------------------------
    for table in (
        "profiles",
        "brands",
        "categories",
        "products",
        "product_variants",
        "store_settings",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON public.{table}")
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_updated_at
                BEFORE UPDATE ON public.{table}
                FOR EACH ROW EXECUTE FUNCTION set_updated_at()
            """
        )

    op.execute(
        """
        CREATE OR REPLACE FUNCTION products_refresh_search_text() RETURNS trigger
        LANGUAGE plpgsql AS $fn$
        BEGIN
            NEW.search_text := lower(
                concat_ws(
                    ' ',
                    NEW.name,
                    NEW.description,
                    NEW.unit_label,
                    array_to_string(NEW.tags, ' ')
                )
            );
            RETURN NEW;
        END;
        $fn$;
        """
    )
    # asyncpg runs each op.execute as a single prepared statement.
    op.execute("DROP TRIGGER IF EXISTS trg_products_search_text ON public.products")
    op.execute(
        """
        CREATE TRIGGER trg_products_search_text
            BEFORE INSERT OR UPDATE OF name, description, unit_label, tags ON public.products
            FOR EACH ROW EXECUTE FUNCTION products_refresh_search_text()
        """
    )
    op.execute(
        "UPDATE public.products SET search_text = lower(concat_ws(' ', name, description, unit_label, array_to_string(tags, ' ')))"
    )

    # --- hardening -----------------------------------------------------------
    op.execute("SELECT app_harden_public_tables()")


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_products_search_text ON public.products")
    op.execute("DROP FUNCTION IF EXISTS products_refresh_search_text()")
    for table in (
        "store_settings",
        "product_variants",
        "products",
        "categories",
        "brands",
        "profiles",
    ):
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON public.{table}")
    op.drop_table("store_settings")
    op.drop_table("product_variants")
    op.drop_table("products")
    op.drop_table("categories")
    op.drop_table("brands")
    op.drop_table("profiles")
    op.execute("DROP TYPE IF EXISTS loyalty_tier")
    op.execute("DROP TYPE IF EXISTS user_role")
