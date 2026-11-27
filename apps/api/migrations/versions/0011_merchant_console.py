"""Add the store-open switch and merchant order workflow states.

Revision ID: 0011_merchant_console
Revises: 0010_offer_push_count
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_merchant_console"
down_revision: str | None = "0010_offer_push_count"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")
    op.add_column(
        "store_settings",
        sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    # Existing orders keep their values; new merchant actions move them through
    # these additional, forward-only enum states.
    op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'accepted'")
    op.execute("ALTER TYPE order_status ADD VALUE IF NOT EXISTS 'packing'")


def downgrade() -> None:
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")
    # PostgreSQL cannot remove enum labels safely. Keep the additive enum values;
    # dropping the newly-added settings column restores the prior schema shape.
    op.drop_column("store_settings", "is_open")
