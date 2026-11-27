"""Add the lightweight assigned-driver order workflow.

Revision ID: 0012_delivery_workflow
Revises: 0011_merchant_console
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012_delivery_workflow"
down_revision: str | None = "0011_merchant_console"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")
    op.add_column(
        "orders",
        sa.Column(
            "assigned_to",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "profiles.id", ondelete="SET NULL", name="fk_orders_assigned_to_profiles"
            ),
            nullable=True,
        ),
    )
    op.add_column("orders", sa.Column("out_for_delivery_at", sa.DateTime(timezone=True)))
    op.add_column("orders", sa.Column("delivered_at", sa.DateTime(timezone=True)))
    op.create_index("ix_orders_assigned_to", "orders", ["assigned_to"])
    op.add_column(
        "store_settings",
        sa.Column(
            "default_delivery_profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "profiles.id",
                ondelete="SET NULL",
                name="fk_store_settings_default_delivery_profile",
            ),
            nullable=True,
        ),
    )

    # A foreign key alone cannot constrain the referenced profile's role. Keep
    # the invariant in Postgres too, so direct SQL cannot assign staff/customer
    # profiles incorrectly or demote a driver while an order/default still uses it.
    op.execute(
        """
        CREATE FUNCTION public.require_delivery_profile_for_order() RETURNS trigger
        LANGUAGE plpgsql SET search_path = public, pg_temp AS $fn$
        BEGIN
            IF NEW.assigned_to IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM public.profiles
                WHERE id = NEW.assigned_to AND role = 'delivery'::public.user_role
            ) THEN
                RAISE EXCEPTION 'assigned_to must reference a delivery profile'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $fn$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_orders_assigned_to_delivery_profile
        BEFORE INSERT OR UPDATE OF assigned_to ON public.orders
        FOR EACH ROW EXECUTE FUNCTION public.require_delivery_profile_for_order()
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.require_default_delivery_profile() RETURNS trigger
        LANGUAGE plpgsql SET search_path = public, pg_temp AS $fn$
        BEGIN
            IF NEW.default_delivery_profile_id IS NOT NULL AND NOT EXISTS (
                SELECT 1 FROM public.profiles
                WHERE id = NEW.default_delivery_profile_id AND role = 'delivery'::public.user_role
            ) THEN
                RAISE EXCEPTION 'default_delivery_profile_id must reference a delivery profile'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $fn$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_store_settings_default_delivery_profile
        BEFORE INSERT OR UPDATE OF default_delivery_profile_id ON public.store_settings
        FOR EACH ROW EXECUTE FUNCTION public.require_default_delivery_profile()
        """
    )
    op.execute(
        """
        CREATE FUNCTION public.protect_assigned_delivery_role() RETURNS trigger
        LANGUAGE plpgsql SET search_path = public, pg_temp AS $fn$
        BEGIN
            IF OLD.role = 'delivery'::public.user_role
               AND NEW.role <> 'delivery'::public.user_role
               AND (
                   EXISTS (SELECT 1 FROM public.orders WHERE assigned_to = OLD.id)
                   OR EXISTS (
                       SELECT 1 FROM public.store_settings
                       WHERE default_delivery_profile_id = OLD.id
                   )
               ) THEN
                RAISE EXCEPTION 'remove delivery assignments before changing the profile role'
                    USING ERRCODE = '23514';
            END IF;
            RETURN NEW;
        END;
        $fn$
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_profiles_protect_delivery_role
        BEFORE UPDATE OF role ON public.profiles
        FOR EACH ROW EXECUTE FUNCTION public.protect_assigned_delivery_role()
        """
    )

    # Supabase REST has no table grants by design. This policy is defense in
    # depth if a future deployment intentionally grants the authenticated role.
    # Plain PostgreSQL test databases do not have auth.uid(), so skip only the
    # policy there; API-level delivery isolation remains tested in both setups.
    op.execute(
        """
        DO $$
        BEGIN
            IF to_regprocedure('auth.uid()') IS NOT NULL
               AND EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                EXECUTE $policy$
                    CREATE POLICY orders_delivery_assigned_only ON public.orders
                    FOR ALL TO authenticated
                    USING (assigned_to = auth.uid())
                    WITH CHECK (assigned_to = auth.uid())
                $policy$;
            END IF;
        END;
        $$
        """
    )
    op.execute("SELECT app_harden_public_tables()")


def downgrade() -> None:
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")
    op.execute("DROP POLICY IF EXISTS orders_delivery_assigned_only ON public.orders")
    op.execute("DROP TRIGGER IF EXISTS trg_profiles_protect_delivery_role ON public.profiles")
    op.execute("DROP FUNCTION IF EXISTS public.protect_assigned_delivery_role()")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_store_settings_default_delivery_profile ON public.store_settings"
    )
    op.execute("DROP FUNCTION IF EXISTS public.require_default_delivery_profile()")
    op.execute("DROP TRIGGER IF EXISTS trg_orders_assigned_to_delivery_profile ON public.orders")
    op.execute("DROP FUNCTION IF EXISTS public.require_delivery_profile_for_order()")
    op.drop_column("store_settings", "default_delivery_profile_id")
    op.drop_index("ix_orders_assigned_to", table_name="orders")
    op.drop_column("orders", "delivered_at")
    op.drop_column("orders", "out_for_delivery_at")
    op.drop_column("orders", "assigned_to")
