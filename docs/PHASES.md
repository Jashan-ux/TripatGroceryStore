# Phases

The brief stops at the end of each phase for review. This table is the live
status board; `docs/ACCEPTANCE_REPORT.md` carries the scenario-level evidence.

| Phase | Scope | Status |
|---|---|---|
| 0 | Monorepo, CI, Supabase local config, Alembic baseline, design tokens, PWA shell, health checks | ✅ **done** — awaiting go-ahead |
| 1 | Auth + profile + catalogue (public pages, categories, brands, search/filters, realistic seed) | ✅ **done** — CI 5/5 green, live seed loaded |
| 2 | Cart, addresses, checkout, COD orders, stock, min-order + pincode rules, customer order pages | ✅ **done** — 0003 applied live, CI green |
| 3 | Admin orders, notifications (in-app, email, red dot), per-order delivery days, customer cancel | ✅ **done** — order queue + transitions (Phase 2), then bell, email outbox, red dots and per-order delivery days; `0004` applied live |
| 4 | Wallet, referrals, scratch cards, returns, loyalty badges | ✅ **done** — wallet ledger + checkout spend, referral programme, server-side scratch cards, two-step returns (approve → received → credit), loyalty tiers; `0005` applied live, rewards hub and admin returns queue shipped |
| 5 | Admin catalogue tools (inline add, bulk add, categories, brands), offers, settings, feedback | ✅ **done** — `0006` applied live (22 tables, 264/264 columns, digest `999d3e5e…2458`); 76 new API tests and 19 new web tests green |
| 5.1 | Hardening: rate limits that actually run (order, feedback, code guessing, uploads) | ✅ **done** — `0007` applied live (23 tables, 268/268 columns, digest `e1e60b83…a0bc97c3`); replaces the un-installed slowapi shell and removes the Redis requirement |
| 6 | Analytics with drill-downs, customer profiles, low-stock edit flow | ✅ **done** — 0008 indexes round-trip locally and are present in Supabase; 14 API scenarios + web coverage for A-10/A-11/A-13; CI 5/5 green |
| 7 | PWA polish: install prompt, web push, offline, Lighthouse | 🟡 **in progress** — install prompt, offer delivery and selective offline caching implemented; CI Playwright and built-bundle Lighthouse gates pass. Vercel connector confirms production is READY/PROMOTED at `81e814b`; the address fix preview at `daae892` is READY/STAGED, not promoted to production. Ordered DB workflow verify → migrate → verify passed using the session pooler; Supabase reports `0010_offer_push_count`, `push_subscriptions` with RLS, and `offers.push_queued`. ORM type/FK autogenerate drift was corrected; latest `verify` passed without the drift warning. Render health/offers, direct Origin-header CORS, VAPID-provider delivery, public-origin Lighthouse/full-site axe remain unverified. |
| 8 | Security hardening, full acceptance run, deploy, DEPLOY.md, ACCEPTANCE_REPORT.md | 🟡 **in progress** — security gates and docs are maintained; admin offer links reject protocol-relative, backslash-confusable, and control-character URLs. Address form regression traced to a duplicate, stale `@hookform/resolvers` dev dependency (3.9.1) overriding the runtime 7.0.9 package; its Zod 4 validation rejection surfaced as an unhandled promise instead of field errors. Lockfile now resolves the Zod-4-compatible runtime package; save errors and post-save UI updates are covered. Production deployment/acceptance still pending. |
| 9 (optional) | Hindi UI, delivery-person role, SMS OTP behind the flag | ⬜ |

## What Phase 0 actually delivers

**Backend (`apps/api`)**

- Typed settings with production validation that refuses to boot with missing
  secrets, a non-HTTPS origin, a wildcard CORS entry, or rate limiting enabled
  without Redis. (`app/core/config.py`)
- One error shape for every failure, including validation and 500s that never
  leak stack traces in production. (`app/core/errors.py`)
- Structured JSON logs with PII/token scrubbing; one access log per request.
  (`app/core/logging.py`)
- Security headers on every response, `/docs` off in production, `X-Request-ID`
  propagation. (`app/core/middleware.py`, `app/main.py`)
- Async SQLAlchemy engine configured for the Supabase transaction pooler
  (`statement_cache_size=0`), separate direct URL for Alembic. (`app/db/session.py`)
- `/healthz` (liveness, component detail) and `/healthz/ready` (503 until the DB
  answers), plus `/api/v1/status` and `/api/v1/config`.
- Alembic baseline: extensions, `set_updated_at()`, and a **DDL event trigger**
  that enables RLS and revokes `anon`/`authenticated` grants on every new public
  table — the Supabase REST API is dark by construction.
- Rate-limit scaffolding (replaced in 5.1 by a Postgres-backed limiter that the
  app actually installs — see below).
- Non-root slim Dockerfile with a healthcheck; `/docs`-free production schema.

**Frontend (`apps/web`)**

- Vite 7 + React 18 + TypeScript strict, Tailwind tokens for brand red
  (`#B91C1C`), Material-style elevation, 44px targets, visible focus, reduced
  motion support.
- Storefront shell: sticky header (logo 110×110, wordmark, bell/profile/cart/menu,
  search), hero banner with tap-to-call, store status strip, mobile bottom nav,
  customer footer — with the `.pb-nav-safe` spacing contract so the fixed nav can
  never cover content or the footer (defect 6.4).
- Lazily-loaded admin bundle with its own shell: top tab strip, mobile bottom nav,
  **no** cart, **no** customer footer, **no** product search (defect 6.4).
- PWA: `vite-plugin-pwa` with `registerType: 'prompt'`, generated
  192/512/maskable icons from the brand artwork, manifest with id/start_url/scope,
  Workbox rules that cache only the app shell, public catalogue GETs and bounded
  public images; checkout, account, admin, all other `/api/*` and Supabase
  responses remain network-only. An optional, dismissible install nudge and
  opt-in web-push settings live in the customer UI; app updates wait for consent.
  Browsed catalogue pages and assets can be revisited offline; orders cannot be
  placed without the server's live stock and price checks.
- Typed API client: types generated from the FastAPI schema
  (`packages/api-client`), an `ApiError` that mirrors the backend error shape, and
  a single `apiFetch` seam (`no-store`, request timeout, abort support).
- Offline banner, error boundary, skeleton loaders, honest empty states, i18n
  scaffold (English dictionary, Hindi-ready).
- Deployment config for both hosts, generated at deploy time from templates.
- Guards: initial JS budget gate (94.1 KB gzip measured, 200 KB budget), ESLint
  with jsx-a11y, Vitest + RTL, Playwright at 360×800 and 1280×800.

## Explicitly **not** in Phase 0 (so nothing is overclaimed)

- No auth, no real catalogue, no cart, no orders, no notifications, no wallet,
  no admin tools, no analytics, no push, no install prompt.
- Sections not yet built render a page that says so and offers tap-to-call; they
  are not broken links and contain no fabricated products or figures.
- `ADMIN_EMAILS` bootstrap and the `profiles` table land in Phase 1 with the auth
  migration.
