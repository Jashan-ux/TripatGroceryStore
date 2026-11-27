"""Owner tools: catalogue edits, offers, settings and the feedback inbox.

Phase 5 schema, and the shape follows one question the owner asked: *"how do I
know what changed?"*

* ``audit_log`` is append-only — no ``updated_at``, no update path — and records
  the actor's email at write time so the row still reads correctly after the
  profile is gone. Every admin mutation in this phase writes exactly one row.
* ``offers`` is the message *and* its reach: who it went to, how many bells rang,
  how many emails were queued. The banner reads the newest live row.
* ``feedback`` keeps a customer's message in the shop's own database instead of
  only in an inbox, with a status the owner can clear.

The revision id is kept short on purpose: ``alembic_version.version_num`` is
``varchar(32)``, and a longer name is a migration that fails on its last
statement (the DDL rolls back, but it fails all the same).

``notification_kind`` gains ``offer`` so the bell can tell a promotion apart from
an order update. Postgres 16 allows ``ADD VALUE`` inside the migration's
transaction as long as the new value is not used in that same transaction — it is
not (offers arrive over HTTP, later).

Revision ID: 0006_owner_tools
Revises: 0005_wallet_referrals_rewards
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_owner_tools"
down_revision: str | None = "0005_wallet_referrals_rewards"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TIMESTAMPED_TABLES = ("offers", "feedback")


def upgrade() -> None:
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")

    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'feedback_kind') THEN
                CREATE TYPE feedback_kind AS ENUM ('general', 'order', 'product', 'other');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'feedback_status') THEN
                CREATE TYPE feedback_status AS ENUM ('new', 'read');
            END IF;
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'offer_audience') THEN
                CREATE TYPE offer_audience AS ENUM ('all', 'gold', 'platinum', 'diamond');
            END IF;
        END $$;
        """
    )
    # The bell needs a kind for "the shop is telling you something".
    op.execute("ALTER TYPE notification_kind ADD VALUE IF NOT EXISTS 'offer'")

    feedback_kind = postgresql.ENUM(name="feedback_kind", create_type=False)
    feedback_status = postgresql.ENUM(name="feedback_status", create_type=False)
    offer_audience = postgresql.ENUM(name="offer_audience", create_type=False)

    op.create_table(
        "audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_email", sa.String(length=320), nullable=False, server_default=""),
        sa.Column("action", sa.String(length=60), nullable=False),
        sa.Column("entity", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("summary", sa.String(length=200), nullable=False, server_default=""),
        sa.Column(
            "before", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "after", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("note", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
    )
    op.create_index("ix_audit_log_created", "audit_log", ["created_at"])
    op.create_index("ix_audit_log_entity", "audit_log", ["entity", "entity_id"])

    op.create_table(
        "offers",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("title", sa.String(length=140), nullable=False),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("href", sa.Text(), nullable=False, server_default="/"),
        sa.Column("audience", offer_audience, nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "sent_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("recipients", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("emails_queued", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
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
        sa.PrimaryKeyConstraint("id", name="pk_offers"),
        sa.CheckConstraint("recipients >= 0", name="ck_offers_recipients_non_negative"),
        sa.CheckConstraint("char_length(title) > 0", name="ck_offers_title_not_empty"),
    )
    op.create_index("ix_offers_created", "offers", ["created_at"])

    op.create_table(
        "feedback",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "profile_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("name", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("phone", sa.String(length=20), nullable=False, server_default=""),
        sa.Column("email", sa.String(length=320), nullable=False, server_default=""),
        sa.Column(
            "kind",
            feedback_kind,
            nullable=False,
            server_default=sa.text("'general'::feedback_kind"),
        ),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "status",
            feedback_status,
            nullable=False,
            server_default=sa.text("'new'::feedback_status"),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "read_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
        sa.PrimaryKeyConstraint("id", name="pk_feedback"),
        sa.CheckConstraint("char_length(message) > 0", name="ck_feedback_message_not_empty"),
    )
    op.create_index("ix_feedback_status_created", "feedback", ["status", "created_at"])

    for table in TIMESTAMPED_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON public.{table}")
        op.execute(
            f"""
            CREATE TRIGGER trg_{table}_updated_at
                BEFORE UPDATE ON public.{table}
                FOR EACH ROW EXECUTE FUNCTION set_updated_at()
            """
        )

    op.execute("SELECT app_harden_public_tables()")


def downgrade() -> None:
    op.execute("SELECT set_config('search_path', 'public, extensions, pg_temp', true)")
    for table in TIMESTAMPED_TABLES:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{table}_updated_at ON public.{table}")

    op.drop_index("ix_feedback_status_created", table_name="feedback")
    op.drop_table("feedback")
    op.drop_index("ix_offers_created", table_name="offers")
    op.drop_table("offers")
    op.drop_index("ix_audit_log_entity", table_name="audit_log")
    op.drop_index("ix_audit_log_created", table_name="audit_log")
    op.drop_table("audit_log")

    op.execute("DROP TYPE IF EXISTS offer_audience")
    op.execute("DROP TYPE IF EXISTS feedback_status")
    op.execute("DROP TYPE IF EXISTS feedback_kind")
    # `notification_kind` keeps 'offer': Postgres cannot remove a value from an
    # enum without recreating the type, and a dormant value is harmless.
