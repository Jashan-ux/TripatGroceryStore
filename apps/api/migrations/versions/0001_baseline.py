"""Baseline: extensions, timestamp trigger, and automatic table hardening.

Nothing business-specific lives here — each phase adds its own revision. What
this revision *does* establish is the security posture that must hold for every
future table:

* ``pgcrypto`` (``gen_random_uuid()``), ``pg_trgm`` + ``unaccent`` (search).
* a ``set_updated_at()`` trigger function used by all tables.
* ``harden_public_table()`` plus an event trigger that runs it for **every**
  table created in ``public``, so a developer can never forget to enable RLS or
  to revoke grants from ``anon`` / ``authenticated``. The Supabase REST API is
  therefore dark by construction: no policies exist for those roles, so
  PostgREST returns nothing even with the public anon key.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-11-25
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

    # --- updated_at maintenance ------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at := now();
            RETURN NEW;
        END;
        $$;
        """
    )

    # --- automatic hardening ---------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION harden_public_table() RETURNS event_trigger
        LANGUAGE plpgsql AS $$
        DECLARE
            obj record;
            role_name text;
        BEGIN
            FOR obj IN SELECT * FROM pg_event_trigger_ddl_commands()
                WHERE command_tag = 'CREATE TABLE'
                  AND schema_name = 'public'
            LOOP
                EXECUTE format('ALTER TABLE %s ENABLE ROW LEVEL SECURITY', obj.object_identity);
                -- Defense in depth: even if a policy is added by mistake, the
                -- auto-generated API roles have no table privileges at all.
                FOREACH role_name IN ARRAY ARRAY['anon', 'authenticated'] LOOP
                    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
                        EXECUTE format(
                            'REVOKE ALL ON TABLE %s FROM %I', obj.object_identity, role_name
                        );
                    END IF;
                END LOOP;
            END LOOP;
        END;
        $$;
        """
    )
    op.execute("DROP EVENT TRIGGER IF EXISTS trg_harden_public_table")
    op.execute(
        """
        CREATE EVENT TRIGGER trg_harden_public_table
        ON ddl_command_end
        WHEN TAG IN ('CREATE TABLE')
        EXECUTE FUNCTION harden_public_table()
        """
    )

    # --- Supabase role hygiene -------------------------------------------------
    # The Supabase REST API roles must never see our data. Service-role usage is
    # limited to Storage uploads performed by the backend.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                EXECUTE 'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM anon';
                EXECUTE 'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon';
                EXECUTE 'REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM anon';
                EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES FROM anon';
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                EXECUTE 'REVOKE ALL ON ALL TABLES IN SCHEMA public FROM authenticated';
                EXECUTE 'REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM authenticated';
                EXECUTE 'REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM authenticated';
                EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
                        'REVOKE ALL ON TABLES FROM authenticated';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP EVENT TRIGGER IF EXISTS trg_harden_public_table")
    op.execute("DROP FUNCTION IF EXISTS harden_public_table()")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
    # Extensions are intentionally left installed: other databases in the same
    # cluster (and Supabase internals) may rely on them.
