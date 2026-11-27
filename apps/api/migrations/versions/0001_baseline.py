"""Baseline: extensions, timestamp trigger, and table hardening.

Nothing business-specific lives here — each phase adds its own revision. What
this revision establishes is the security posture that must hold for every
future table:

* ``pg_trgm`` + ``unaccent`` for search (installed into the ``extensions``
  schema on Supabase, ``public`` on a plain Postgres).
* a ``set_updated_at()`` trigger function used by all tables.
* ``app_harden_public_tables()``, which enables RLS and revokes every grant from
  ``anon`` / ``authenticated`` on all tables in ``public``. Every later migration
  calls it at the end, and ``tests/test_rls.py`` fails the build if any table is
  left unhardened.

Why a function and not a DDL event trigger: creating event triggers requires a
superuser, and the Supabase ``postgres`` role is not one (verified:
``current_setting('is_superuser') = off``).

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
    # --- extensions -----------------------------------------------------------
    # Supabase keeps extensions in a dedicated schema; plain Postgres does not.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'extensions') THEN
                EXECUTE 'CREATE EXTENSION IF NOT EXISTS pg_trgm SCHEMA extensions';
                EXECUTE 'CREATE EXTENSION IF NOT EXISTS unaccent SCHEMA extensions';
            ELSE
                EXECUTE 'CREATE EXTENSION IF NOT EXISTS pg_trgm';
                EXECUTE 'CREATE EXTENSION IF NOT EXISTS unaccent';
            END IF;
        END $$;
        """
    )

    # --- updated_at maintenance ----------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger
        LANGUAGE plpgsql AS $fn$
        BEGIN
            NEW.updated_at := now();
            RETURN NEW;
        END;
        $fn$;
        """
    )

    # --- hardening ------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE FUNCTION app_harden_public_tables() RETURNS void
        LANGUAGE plpgsql SECURITY DEFINER SET search_path = public, pg_temp AS $fn$
        DECLARE
            t record;
            has_anon boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon');
            has_authed boolean := EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated');
        BEGIN
            FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
                EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.tablename);
                IF has_anon THEN
                    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM anon', t.tablename);
                END IF;
                IF has_authed THEN
                    EXECUTE format('REVOKE ALL ON TABLE public.%I FROM authenticated', t.tablename);
                END IF;
            END LOOP;

            FOR t IN SELECT sequencename FROM pg_sequences WHERE schemaname = 'public' LOOP
                IF has_anon THEN
                    EXECUTE format('REVOKE ALL ON SEQUENCE public.%I FROM anon', t.sequencename);
                END IF;
                IF has_authed THEN
                    EXECUTE format(
                        'REVOKE ALL ON SEQUENCE public.%I FROM authenticated', t.sequencename
                    );
                END IF;
            END LOOP;

            -- Applies to tables created later by this role as well.
            IF has_anon THEN
                EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
                        'REVOKE ALL ON TABLES FROM anon';
                EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
                        'REVOKE ALL ON SEQUENCES FROM anon';
            END IF;
            IF has_authed THEN
                EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
                        'REVOKE ALL ON TABLES FROM authenticated';
                EXECUTE 'ALTER DEFAULT PRIVILEGES IN SCHEMA public '
                        'REVOKE ALL ON SEQUENCES FROM authenticated';
            END IF;
        END;
        $fn$;
        """
    )
    op.execute("SELECT app_harden_public_tables()")


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS app_harden_public_tables()")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at()")
    # Extensions are intentionally left installed: Supabase internals may use them.
