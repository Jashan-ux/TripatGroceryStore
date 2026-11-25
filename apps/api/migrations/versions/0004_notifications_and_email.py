"""In-app notifications and the email outbox.

Phase 3 schema. Two notes that matter:

* ``notifications`` cascades with the profile and nulls its ``order_id`` if an
  order ever disappears, so a bell entry can never block a delete.
* ``email_messages.dedupe_key`` is unique. The flush is therefore idempotent: a
  retry after a crash cannot send the same confirmation twice, and the same event
  can never queue two copies.

Revision ID: 0004_notifications_and_email
Revises: 0003_orders_and_addresses
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_notifications_and_email"
down_revision: str | None = "0003_orders_and_addresses"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'notification_kind') THEN
                CREATE TYPE notification_kind AS ENUM (
                    'order_placed', 'order_status', 'order_cancelled', 'new_order', 'system'
                );
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'email_status') THEN
                CREATE TYPE email_status AS ENUM ('queued', 'sent', 'skipped', 'failed');
            END IF;
        END $$;
        """
    )

    notification_kind = postgresql.ENUM(
        "order_placed",
        "order_status",
        "order_cancelled",
        "new_order",
        "system",
        name="notification_kind",
        create_type=False,
    )
    email_status = postgresql.ENUM(
        "queued", "sent", "skipped", "failed", name="email_status", create_type=False
    )

    op.create_table(
        "notifications",
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
        sa.Column("kind", notification_kind, nullable=False),
        sa.Column("title", sa.String(length=140), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("href", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
    )
    op.create_index(
        "ix_notifications_profile_created", "notifications", ["profile_id", "created_at"]
    )
    op.create_index("ix_notifications_unread", "notifications", ["profile_id", "read_at"])

    op.create_table(
        "email_messages",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("to_email", sa.String(length=320), nullable=False),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body_text", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "status", email_status, nullable=False, server_default=sa.text("'queued'::email_status")
        ),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("last_error", sa.Text(), nullable=False, server_default=""),
        sa.Column("dedupe_key", sa.String(length=200), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_email_messages"),
        sa.UniqueConstraint("dedupe_key", name="uq_email_messages_dedupe_key"),
    )
    op.create_index("ix_email_messages_status_created", "email_messages", ["status", "created_at"])

    for table in ("notifications", "email_messages"):
        op.execute(
            f"""
            DROP TRIGGER IF EXISTS trg_{table}_updated_at ON public.{table};
            CREATE TRIGGER trg_{table}_updated_at
                BEFORE UPDATE ON public.{table}
                FOR EACH ROW EXECUTE FUNCTION set_updated_at();
            """
        )

    # RLS + revoked grants for the new tables (the baseline installs the guard).
    op.execute("SELECT app_harden_public_tables()")


def downgrade() -> None:
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")
    op.drop_index("ix_email_messages_status_created", table_name="email_messages")
    op.drop_table("email_messages")
    op.drop_index("ix_notifications_unread", table_name="notifications")
    op.drop_index("ix_notifications_profile_created", table_name="notifications")
    op.drop_table("notifications")
    op.execute("DROP TYPE IF EXISTS email_status")
    op.execute("DROP TYPE IF EXISTS notification_kind")
