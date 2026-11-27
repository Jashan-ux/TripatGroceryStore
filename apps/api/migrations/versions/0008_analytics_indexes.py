"""Indexes the analytics screens need (Phase 6).

Phase 6 reads the shop the other way round for the first time: instead of "this
customer's orders", it asks "every order in these days", "what sold", and "who
spends most". Two indexes carry those:

* ``ix_orders_placed`` on ``orders(placed_at)`` — the range scan behind the
  revenue card, the daily series and the drill-down. Without it every screen is a
  sequential scan of the order tables, which is fine at 200 rows and not fine at
  20,000 — and the owner will reach 20,000 before anyone reopens this file.
* ``ix_order_items_product_order`` on ``order_items(product_id, order_id)`` — the
  "what actually sold" rollup joins lines back to orders by date.

Nothing is dropped: the existing ``(status, placed_at)`` and
``(profile_id, placed_at)`` indexes still serve the order queue and a single
customer's history.

Revision ID: 0008_analytics_indexes
Revises: 0007_rate_limits
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008_analytics_indexes"
down_revision: str | None = "0007_rate_limits"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")
    op.create_index("ix_orders_placed", "orders", ["placed_at"])
    op.create_index("ix_order_items_product_order", "order_items", ["product_id", "order_id"])


def downgrade() -> None:
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")
    op.drop_index("ix_order_items_product_order", table_name="order_items")
    op.drop_index("ix_orders_placed", table_name="orders")
