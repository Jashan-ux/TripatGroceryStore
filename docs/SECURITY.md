# Security

Acceptance criteria are mapped to code **and** to a test. A control without a
test is listed as such — no control is claimed as done because it "looks right".

Status legend: ✅ implemented and tested · 🟡 implemented, test lands with its
phase · ⬜ not yet built (phase in brackets).

## ASVS L1 / OWASP Top 10 mapping

| # | Control | Code | Test | Status |
|---|---|---|---|---|
| V1 | Central error handling, no internals leaked | `app/core/errors.py` | `tests/test_errors.py` | ✅ |
| V1 | Production hides `/docs`, `/redoc`, `/openapi.json` | `app/main.py` (`docs_enabled`) | `tests/test_errors.py::test_docs_hidden_in_production` | ✅ |
| V1 | Fail-fast production config validation | `app/core/config.py::_validate_runtime` | `tests/test_config.py` | ✅ |
| V1 | Structured logs without PII/tokens | `app/core/logging.py` | `tests/test_logging.py` | ✅ |
| V2 | Password policy delegated to Supabase Auth (min 8, breached-password check) | Supabase project settings | manual checklist | 🟡 (1) |
| V2 | JWT verified on every protected route: JWKS signature, `iss`, `aud`, `exp`, `nbf` | `app/core/auth.py` | `tests/test_auth.py` | ⬜ (1) |
| V2 | Role **only** from `profiles.role`, never from JWT metadata | `app/core/auth.py`, `app/services/profiles.py` | `tests/test_auth.py::test_metadata_role_ignored` | ⬜ (1) |
| V2 | Admin bootstrap from `ADMIN_EMAILS` at seed time only | `app/scripts/seed.py` | `tests/test_seed.py` | ⬜ (1) |
| V2 | TOTP MFA available for admin | Supabase Auth MFA + admin settings screen | manual checklist | ⬜ (1) |
| V2 | Google sign-in only with a verified email | `app/core/auth.py` (checks `email_verified`) | `tests/test_auth.py` | ⬜ (1) |
| V3 | Session persists via refresh tokens; logout revokes | Supabase JS + `useSession` | `e2e/auth.spec.ts` (C‑05) | ⬜ (1) |
| V4 | Deny by default; **one** admin dependency on all admin routers | `app/api/deps.py::require_admin` | `tests/test_authz.py::test_admin_routes_require_admin` | ⬜ (1) |
| V4 | Ownership inside the SQL `WHERE`, never post-fetch filtering | `app/repositories/*` | `tests/test_idor.py` (S‑02) | ⬜ (2) |
| V4 | No admin code in the customer bundle | `src/App.tsx` (lazy import) + separate chunk | `e2e/shell.spec.ts::admin bundle is not part of the customer page load` | ✅ |
| V5 | Strict Pydantic models: length, range, enum, `extra="forbid"` | `app/schemas/*` | `tests/test_schemas.py` | ✅ (base) |
| V5 | Parameterised SQL only (SQLAlchemy Core/ORM, no string SQL from input) | `app/repositories/*` | `tests/test_sqli.py` (S‑07) | ⬜ (1) |
| V5 | SSRF guard on every server-side URL fetch (https only, no private IPs, size/type limits) | `app/services/images.py` | `tests/test_images.py` (A‑08, S‑08) | ⬜ (5) |
| V5 | Uploads re-encoded; magic-byte check; no SVG | `app/services/images.py` | `tests/test_images.py` | ⬜ (5) |
| V5 | HTML-escaped user text in emails; no `dangerouslySetInnerHTML` anywhere | `app/services/email.py`; ESLint `no-danger` audit | `tests/test_email_templates.py` | ⬜ (3) |
| V6 | No secrets in repo (gitleaks pre-commit + CI), `.env.example` only | `.gitleaks.toml`, `.pre-commit-config.yaml`, CI `security` job | CI job `Security · secrets, audits, headers` | ✅ |
| V6 | No secrets in the client bundle | CI greps `apps/web/dist` for service-role strings | CI `No secrets in the built bundle` | ✅ |
| V7 | Security headers: CSP (no inline scripts), HSTS, `X-Content-Type-Options`, `Referrer-Policy`, `frame-ancestors 'none'`, `Permissions-Policy(geolocation=(self))` | `app/core/middleware.py` + `vercel.json.template` / `netlify.toml.template` | `tests/test_health.py::test_security_headers_present`, `tests/test_headers.py` | ✅ (API), 🟡 (host config) |
| V7 | No third-party scripts or analytics tags | `index.html` (no external `<script>`) | `e2e/shell.spec.ts` | ✅ |
| V8 | Idempotency on order placement and every credit | `Idempotency-Key` + unique indexes | `tests/test_orders.py::test_double_click_single_order` (C‑09), `test_returns.py::test_credit_replay_safe` (A‑12) | ⬜ (2, 4) |
| V8 | `SELECT … FOR UPDATE` around stock and wallets | `app/services/checkout.py` | `tests/test_concurrency.py` (S‑04) | ⬜ (2) |
| V8 | DB constraints: `CHECK (stock >= 0)`, `wallet >= 0`, `qty > 0`; unique referral/scratch/return-credit | `app/models/*` + Alembic | `tests/test_constraints.py` | ⬜ (1–4) |
| V9 | No sensitive data in logs; `X-Request-ID` for correlation | `app/core/logging.py`, `app/core/middleware.py` | `tests/test_logging.py` | ✅ |
| V10 | Integration libs pinned; Dependabot; `npm audit`/`pip-audit` in CI | `package-lock.json`, `pyproject.toml`, `.github/workflows/ci.yml` | CI `security` job | ✅ |
| V11 | Every admin and credit action written to `audit_log` | `app/services/audit.py` | `tests/test_audit.py` (S‑12) | ⬜ (3) |
| V12 | Same-origin API via rewrites; CORS allowlist only (never `*` with credentials) | `vercel.json.template`, `netlify.toml.template`, `app/main.py` | `tests/test_config.py::test_wildcard_cors_is_rejected` | ✅ |
| V13 | Rate limits per IP and per user, Redis-backed; boot refuses memory store in production | `app/core/rate_limit.py`, `app/core/config.py` | `tests/test_rate_limit.py` (S‑06) | 🟡 |
| V13 | Turnstile on signup and feedback | `app/services/turnstile.py` | `tests/test_turnstile.py` | ⬜ (1, 5) |
| V13 | Referral/coupon guessing throttled; referral fraud flags | `app/services/referrals.py` | `tests/test_referrals.py` (C‑13) | ⬜ (4) |
| V14 | Supabase RLS on every public table, no `anon`/`authenticated` policies, grants revoked (auto-applied by DDL trigger) | `migrations/versions/0001_baseline.py` | `tests/test_rls.py::test_anon_gets_nothing` (S‑01) | 🟡 (trigger installed; test in 1) |
| V14 | HTTPS + HSTS only; `upgrade-insecure-requests` | host config + `middleware.py` | `tests/test_headers.py`; securityheaders.com **A** | 🟡 (host config) |
| DPDP | Privacy policy + terms pages; notification consent; account export & deletion; minimal data | `src/pages/policies/*`, `app/api/v1/endpoints/me.py` | `tests/test_privacy.py` | ⬜ (8) |
| DPDP | Sentry with PII scrubbing (`send_default_pii=False`, no bodies, no breadcrumbs) | `app/main.py::_init_sentry` | `tests/test_sentry.py` | 🟡 |
| Ops | Structured logs, audit log, backups + restore drill, no debug in production | `docs/DEPLOY.md` §Backups | manual checklist | ⬜ (8) |

## What is *actually* verified today

Run in this workspace on 2026-11-25:

- `ruff check` + `ruff format --check` — clean.
- `mypy app` (strict) — clean, 25 files.
- `pytest` — 27 passed.
- `npx tsc --noEmit` (strict, `noUncheckedIndexedAccess`) — clean.
- `eslint . --max-warnings 0` (incl. `jsx-a11y`) — clean.
- `vitest run` — 22 passed.
- `vite build` + bundle budget — 94.1 KB gzip initial JS (budget 200 KB).
- Docker build, Playwright, Postgres-backed tests: **not run here** (no Docker, no
  browser, no Postgres in this environment) — they run in CI on every push.

## Threat notes

- **XSS is the crown jewel.** Supabase JS keeps the session in `localStorage`, so
  any script injection is session theft. Mitigations: strict CSP without
  `unsafe-inline` for scripts, no third-party scripts, React escaping everywhere,
  no `dangerouslySetInnerHTML`, HTML-escaped email templates, and a CI grep for
  `dangerouslySetInnerHTML` and inline `<script>`.
- **`anon` key exposure is expected; data exposure is not.** The key ships in the
  bundle by design. RLS with no policies plus revoked grants means PostgREST
  returns nothing even with a valid anon JWT.
- **Referral and scratch-card abuse** is the main business-logic risk. Payout on
  delivery (not placement), unique indexes for one-referral-per-user and
  one-card-per-order, server-chosen card amounts, and single-use coupons.
- **Race conditions** on the last unit are handled with `SELECT … FOR UPDATE` plus
  `CHECK (stock >= 0)`; the loser gets `insufficient_stock`, not a negative stock.

## Reporting

Complaints and security reports: **tripatinsan029@gmail.com** (owner-configured in
`store_settings.feedback_email`).
