"""Record how many opted-in browser endpoints an offer targets (Phase 7).

Revision ID: 0010_offer_push_count
Revises: 0009_push_subscriptions
Create Date: 2026-11-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0010_offer_push_count"
down_revision: str | None = "0009_push_subscriptions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")
    op.add_column(
        "offers",
        sa.Column("push_queued", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.create_check_constraint("ck_offers_push_queued_non_negative", "offers", "push_queued >= 0")


def downgrade() -> None:
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")
    op.drop_constraint("ck_offers_push_queued_non_negative", "offers", type_="check")
    op.drop_column("offers", "push_queued")
