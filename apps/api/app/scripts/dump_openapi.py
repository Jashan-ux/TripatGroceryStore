"""Write the OpenAPI schema to disk so the frontend can generate its types.

Usage::

    python -m app.scripts.dump_openapi ../../packages/api-client/openapi.json

The schema is the single source of truth for API types: `packages/api-client`
runs `openapi-typescript` over this file, and no API types are hand-written.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    target = Path(args[0]) if args else Path("openapi.json")
    os.environ.setdefault("ENVIRONMENT", "local")

    from app.main import create_app

    app = create_app()
    schema = app.openapi()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {target} ({len(schema.get('paths', {}))} paths)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
