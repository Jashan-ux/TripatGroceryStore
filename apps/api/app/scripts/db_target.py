"""Print where the database connection points, without the password.

Run from ``apps/api``: ``python -m app.scripts.db_target``. Used by the DB ops
workflow so a run states its target in the log before touching anything.
"""

from __future__ import annotations

import os
import urllib.parse


def describe(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    database = parsed.path.lstrip("/") or "?"
    return (
        f"host={parsed.hostname} port={parsed.port} db={database} "
        f"user={parsed.username} ssl={parsed.query or 'default'}"
    )


def main() -> int:
    url = os.environ.get("DATABASE_URL") or ""
    if not url:
        print("DATABASE_URL is not set")
        return 1
    print(describe(url))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
