"""Small operational CLI: ``python -m app.cli <command>``.

Commands:

* ``openapi`` — dump the schema (used by the type-generation step).
* ``doctor``  — print effective, non-secret configuration and probe the DB.
* ``seed``    — create staging users and a realistic catalogue (Phase 1).
              Refuses to run when ENVIRONMENT=production.
"""

from __future__ import annotations

import asyncio
import sys

USAGE = "usage: python -m app.cli [openapi|doctor|seed]"


def _openapi() -> int:
    from app.scripts.dump_openapi import main as dump

    return dump(sys.argv[2:])


async def _doctor() -> int:
    from app.core.config import get_settings
    from app.db.session import ping_database

    settings = get_settings()
    print(f"environment      : {settings.ENVIRONMENT}")
    print(f"api version      : {__import__('app').__version__}")
    print(f"database         : {'configured' if settings.DATABASE_URL else 'MISSING'}")
    print(f"database direct  : {'configured' if settings.DATABASE_DIRECT_URL else 'fallback'}")
    print(f"supabase url     : {settings.SUPABASE_URL or 'MISSING'}")
    window = settings.RATE_LIMIT_WINDOW_SECONDS
    print(
        f"rate limiting    : {settings.RATE_LIMIT_ENABLED} "
        f"(window={window}s, feedback={settings.RATE_LIMIT_FEEDBACK}, "
        f"orders={settings.RATE_LIMIT_ORDERS})"
    )
    print(f"admin emails     : {len(settings.admin_emails)}")
    if settings.DATABASE_URL:
        ok = await ping_database()
        print(f"db ping          : {'ok' if ok else 'FAILED'}")
        return 0 if ok else 1
    return 0


def _seed() -> int:
    from app.core.config import get_settings

    settings = get_settings()
    if settings.is_production:
        print("refusing to seed in production", file=sys.stderr)
        return 2
    print("seed not implemented yet (Phase 1)", file=sys.stderr)
    return 2


def main() -> int:
    argv = sys.argv[1:]
    if not argv:
        print(USAGE, file=sys.stderr)
        return 2
    command = argv[0]
    if command == "openapi":
        return _openapi()
    if command == "doctor":
        return asyncio.run(_doctor())
    if command == "seed":
        return _seed()
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
