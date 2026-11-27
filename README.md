# Tripat Pansari · MSG Store

A production-grade Progressive Web App for a real shop in Mandi Dabwali, Haryana:
a customer storefront, a merchant admin console, and a FastAPI backend on
Supabase Postgres.

**Cash on delivery only. No payment gateway. No delivery charge.**

|                      |                                                                                                   |
| -------------------- | ------------------------------------------------------------------------------------------------- |
| Shop                 | Tripat Pansari MSG Store, near Sabji Mandi, opposite Gyani Achhar Bhandaar, Mandi Dabwali, 125104 |
| Phone                | +91 87089-73386                                                                                   |
| Serviceable pincodes | 125104, 125201                                                                                    |
| Minimum order        | ₹500 (subtotal)                                                                                   |

## Layout

```
apps/web              React 18 + Vite + TypeScript PWA (customer + lazily-loaded admin)
apps/api              FastAPI + SQLAlchemy 2 async + Alembic (all business rules)
packages/api-client   Types generated from the FastAPI OpenAPI schema
supabase              Supabase CLI config for local Auth/Storage
infra                 docker-compose, Render/Fly/Railway blueprints
docs                  architecture, API, security, deploy, acceptance
reference             the original requirement capture (read-only)
```

## Quick start (local)

```bash
# 1. Toolchain
node --version   # 22.x
python --version # 3.12 (3.11 also works; the container runs 3.12)

# 2. Local Supabase (Auth + Storage + Postgres)
supabase start
supabase status           # note API URL, anon key, service_role key

# 3. Backend
cd apps/api
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env      # fill DATABASE_DIRECT_URL, SUPABASE_* from `supabase status`
alembic upgrade head      # Alembic owns the schema
uvicorn app.main:app --reload --port 8000
#   → http://localhost:8000/healthz   (docs at /docs outside production)

# 4. Frontend
cd ../web
npm install
cp .env.example .env.local
npm run icons             # regenerate PWA icons from public/brand/logo.svg
npm run dev               # → http://localhost:5173 (proxies /api → :8000)
```

Full instructions, including the no-Docker path, are in
[docs/DEPLOY.md](docs/DEPLOY.md).

## Tests

```bash
cd apps/api && pytest                 # unit + API behaviour
cd apps/web && npm run test           # Vitest + React Testing Library
cd apps/web && npm run test:e2e       # Playwright at 360×800 and 1280×800
npm run typecheck && npm run lint     # tsc strict + ESLint
cd apps/web && node scripts/check-bundle-size.mjs   # P‑01 JS budget
```

Tests that need a real Postgres are marked `db` and are skipped (loudly, with a
reason) unless `TEST_DATABASE_URL` is set — see [docs/TESTING.md](docs/TESTING.md).

## Documentation

| Doc                                                    | Contents                                                 |
| ------------------------------------------------------ | -------------------------------------------------------- |
| [docs/PHASES.md](docs/PHASES.md)                       | Phase plan, what is built, what is deliberately deferred |
| [docs/OWNER_CHECKLIST.md](docs/OWNER_CHECKLIST.md)     | Everything only the shop owner can do                    |
| [docs/ASSUMPTIONS.md](docs/ASSUMPTIONS.md)             | Decisions taken where the brief was silent               |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)           | Layers, data model (Mermaid ER), request flow            |
| [docs/API.md](docs/API.md)                             | Generated API reference and conventions                  |
| [docs/SECURITY.md](docs/SECURITY.md)                   | OWASP/ASVS mapping, code + test for every control        |
| [docs/DEPLOY.md](docs/DEPLOY.md)                       | Click-by-click runbook, custom domain, rollback          |
| [docs/TESTING.md](docs/TESTING.md)                     | Test strategy, markers, sinks, manual checklist          |
| [docs/ACCEPTANCE_REPORT.md](docs/ACCEPTANCE_REPORT.md) | Pass/fail per scenario ID with evidence                  |

## Conventions

- Money is **integer paise** (`BIGINT`) everywhere; formatting to ₹ happens only at render.
- Timestamps are `timestamptz` UTC; the UI renders in `Asia/Kolkata`.
- The server decides every price, total, discount, wallet balance and stock level.
  Client-sent amounts are ignored (S‑03).
- One error shape: `{"error": {"code", "message", "details", "request_id"}}`.
- Conventional commits, small and focused: `feat(web): …`, `fix(api): …`, `chore(ci): …`.

## Licence

Proprietary — © Tripat Pansari · MSG Store. Not for redistribution.
