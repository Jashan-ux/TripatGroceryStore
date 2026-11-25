"""Rate-limit counters, counted in Postgres instead of a cache nobody bought.

Phase 5 left a limiter in the tree that the app never installed, and whose storage
was Redis — so "rate limiting" was a comment in the docs and a production boot
that would fail without an Upstash URL. This revision creates the one table that
makes it real:

* ``rate_limit_counters`` is keyed by ``(bucket, window_start)``. The window is
  aligned to the clock, so every worker computes the same boundary with no shared
  state and no coordination; a hit is one ``INSERT … ON CONFLICT DO UPDATE``.
* ``window_end`` is stored rather than recomputed, because ``Retry-After`` is a
  promise to the caller and should not depend on which process answered.
* Rows are swept an hour after their window closes (``app.core.rate_limit``),
  so the table is self-limiting — no cron, no TTL, nothing to remember.

RLS is enabled by the same hardening call as every other table: this is an
internal table, and the PostgREST roles must not be able to read who is hitting
the shop.

Revision ID: 0007_rate_limits
Revises: 0006_owner_tools
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_rate_limits"
down_revision: str | None = "0006_owner_tools"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")

    op.create_table(
        "rate_limit_counters",
        sa.Column("bucket", sa.String(length=120), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.PrimaryKeyConstraint("bucket", "window_start", name="pk_rate_limit_counters"),
        sa.CheckConstraint("hits >= 1", name="hits_positive"),
    )
    op.create_index("ix_rate_limit_counters_window_end", "rate_limit_counters", ["window_end"])

    op.execute("SELECT app_harden_public_tables()")


def downgrade() -> None:
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")
    op.drop_index("ix_rate_limit_counters_window_end", table_name="rate_limit_counters")
    op.drop_table("rate_limit_counters")
