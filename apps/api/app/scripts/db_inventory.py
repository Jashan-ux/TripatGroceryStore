"""Inventory of the live database: catalogue counts and the security posture.

Run from ``apps/api``: ``python -m app.scripts.db_inventory``. Exits nonzero when
a guard fails (row level security off somewhere, or PostgREST roles still hold
table grants), so the DB ops workflow fails instead of printing a green table
next to a broken schema.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text

from app.db.session import dispose_engine, get_sessionmaker

QUERIES: dict[str, str] = {
    "categories": "select count(*) from public.categories",
    "brands": "select count(*) from public.brands",
    "products": "select count(*) from public.products where is_active",
    "variants": "select count(*) from public.product_variants",
    "rls_off": (
        "select count(*) from pg_class c "
        "join pg_namespace n on n.oid = c.relnamespace "
        "where n.nspname = 'public' and c.relkind = 'r' and not c.relrowsecurity"
    ),
    "api_grants": (
        "select count(*) from information_schema.role_table_grants "
        "where table_schema = 'public' and grantee in ('anon', 'authenticated')"
    ),
}

#: Anything above zero here is a security regression.
MUST_BE_ZERO = ("rls_off", "api_grants")


async def main() -> int:
    failures: list[str] = []
    async with get_sessionmaker()() as session:
        for label, sql in QUERIES.items():
            value = await session.scalar(text(sql))
            print(f"{label:<12} {value}")
            if label in MUST_BE_ZERO and value:
                failures.append(label)
    await dispose_engine()

    if failures:
        print(f"::error::guard failed: {', '.join(failures)} must be zero")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
