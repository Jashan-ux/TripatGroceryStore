"""Store browser push subscriptions (Phase 7).

Revision ID: 0009_push_subscriptions
Revises: 0008_analytics_indexes
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_push_subscriptions"
down_revision: str | None = "0008_analytics_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")
    op.create_table(
        "push_subscriptions",
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
        sa.Column("endpoint", sa.Text(), nullable=False),
        sa.Column("p256dh", sa.Text(), nullable=False),
        sa.Column("auth", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.UniqueConstraint("endpoint", name="uq_push_subscriptions_endpoint"),
    )
    op.create_index("ix_push_subscriptions_profile", "push_subscriptions", ["profile_id"])
    op.execute(
        """
        CREATE TRIGGER trg_push_subscriptions_updated_at
            BEFORE UPDATE ON public.push_subscriptions
            FOR EACH ROW EXECUTE FUNCTION set_updated_at()
        """
    )
    # The shared hardener enables RLS and revokes Supabase browser-role grants;
    # only the FastAPI database owner touches this secret-bearing table.
    op.execute("SELECT app_harden_public_tables()")


def downgrade() -> None:
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")
    op.execute(
        "DROP TRIGGER IF EXISTS trg_push_subscriptions_updated_at ON public.push_subscriptions"
    )
    op.drop_index("ix_push_subscriptions_profile", table_name="push_subscriptions")
    op.drop_table("push_subscriptions")
