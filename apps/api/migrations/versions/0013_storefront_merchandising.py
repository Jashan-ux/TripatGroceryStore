"""Add merchant-controlled featured visibility and storefront ordering.

Revision ID: 0013_storefront_merchandising
Revises: 0012_delivery_workflow
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013_storefront_merchandising"
down_revision: str | None = "0012_delivery_workflow"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")
    op.add_column(
        "products",
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "products",
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default=sa.text("1000")),
    )
    op.create_index(
        "ix_products_storefront_order", "products", ["is_active", "is_featured", "sort_order"]
    )


def downgrade() -> None:
    op.drop_index("ix_products_storefront_order", table_name="products")
    op.drop_column("products", "sort_order")
    op.drop_column("products", "is_featured")
