# Acceptance report

Rule: **never mark a scenario passed without running it.** `PASS` requires
evidence in this file — a command output recorded here or a CI run link.
Everything else is `NOT RUN` (with the phase that will exercise it) or
`PARTIAL`.

- Report date: **2026-11-25**
- Phase: **1 — auth, profile and catalogue** (of 8). Phase 0 is closed.
- Branch: `arena/660db374-tripatgrocerystore`
- Environment of record: this sandbox (Node 22.22, Python 3.11, no Docker, no
  browser, no Postgres, **no outbound Postgres to Supabase**) plus GitHub
  Actions, which has a real Postgres service container, a real browser and
  network access to the audit APIs.
- Live project: Supabase `tripat-msgstore`
  (`nhmymidaebfbrbrovbzm`, `ap-south-1`).

## Evidence recorded for Phase 0 and Phase 1

Everything below was run in this session. API numbers come from the sandbox
venv; the `db`-marked tests run in CI, where a Postgres exists.

| Check | Command | Result |
|---|---|---|
| API lint + format | `cd apps/api && ruff check . && ruff format --check .` | ✅ clean (60 files formatted) |
| API types | `cd apps/api && mypy app` | ✅ `no issues found in 45 source files` |
| API tests (local) | `cd apps/api && pytest` | ✅ **226 passed, 16 skipped** — the 16 are the `db` tests, which skip without `TEST_DATABASE_URL` |
| API tests (CI, real Postgres) | CI job *API · lint, types, tests* | ✅ 16 db tests run after `alembic upgrade head` → `downgrade base` → `upgrade head` |
| Python dependency audit | `pip-audit --skip-editable` | ✅ `No known vulnerabilities found` |
| Web types | `npm run typecheck` | ✅ clean (web + api-client) |
| Web lint | `npm run lint` | ✅ clean, `--max-warnings 0` |
| Web unit tests | `npm test` | ✅ `3 files, 22 tests passed` |
| Production build | `npm run build` | ✅ 1888 modules, SW + manifest, 28 precache entries |
| Bundle budget (P‑01) | `node apps/web/scripts/check-bundle-size.mjs` | ✅ **176.8 KB / 200 KB** gzip initial JS |
| Node dependency audit | `npm audit` | ✅ **0 vulnerabilities** |
| Secret scan | `gitleaks detect --log-opts=--all` (CI) | ✅ clean across all history |
| Schema/type sync | `python -m app.scripts.dump_openapi` + `npm run api:types` | ✅ 14 paths, 13 aliases, no drift |
| CI run | [45606217770](https://github.com/Jashan-ux/TripatGroceryStore/actions/runs/45606217770) | ✅ **5/5 jobs green** — Web, API, API container, Security, E2E |
| Live schema inventory | SQL via the Supabase connector | ✅ 6 tables + `alembic_version`, 21 indexes, 3 functions, extensions `pg_trgm`, `unaccent`, `pg_net` |
| Live seed | SQL via the Supabase connector | ✅ 41 categories (10 departments), 30 brands, 70 products (12 unbranded), 44 variants |
| Live drift check | SQLAlchemy metadata (83 columns) vs `information_schema` | ✅ 83/83 — no missing, no extra column |
| Live security posture | SQL via the Supabase connector | ✅ RLS on 7/7 tables, 0 grants to `anon`/`authenticated`, `alembic_version` = `0002_profiles_and_catalogue` |

### Two things this sandbox cannot prove, and how they are covered

1. **Browser against live data.** The sandbox has no browser and cannot open a
   Postgres connection to `*.supabase.co` (`ConnectionResetError` on the TLS
   upgrade), so no preview here is backed by the hosted catalogue. The same code
   paths are exercised instead by the 16 CI database tests and the Playwright
   job (which runs the real API and the real built bundle).
2. **Real sign-in round trip.** Supabase Auth is only reachable from a browser
   with network access. The JWT verification side *is* covered
   (`tests/test_security_jwt.py`) and the profile/role/phone logic is covered
   against Postgres (`tests/test_api_db.py`); the Supabase-hosted login form
   itself needs the deployed site or the owner's machine.

## Customer journey

| ID | Scenario | Status | Evidence / why not |
|---|---|---|---|
| C-01 | Guest opens the store: skeletons then catalogue; rails slide; never scrolls sideways | **PASS (API + shell)** | `tests/test_api_db.py::test_home_returns_categories_and_rails` (rails carry products from a department's subcategories — live data files every product under a subcategory, so this was a real bug), `test_category_listing_is_scoped_to_the_category`; `e2e/shell.spec.ts` asserts hero, tap-to-call and zero horizontal overflow at 360 px. |
| C-02 | Search "ghee", filter by brand/price, sort, empty state | **PASS (API)**, UI in browser not observed | `test_search_matches_partial_words`, `test_search_is_case_insensitive`, `test_in_stock_filter_excludes_zero_stock`, `test_price_filter_and_sorting`, `test_pagination_metadata`; search page wiring has unit coverage for URL state. |
| C-03 | ADD becomes stepper, no reload, count/sticky bar/toast update | **NOT RUN** (Phase 2) | |
| C-04 | Guest cart survives reload, merges on login | **NOT RUN** (Phase 2) | |
| C-05 | Email signup logs in; survives reload and browser restart | **NOT RUN** (needs a browser with Supabase reachability) | Provider config, redirect URLs and the session store are wired; see the limitation above. |
| C-06 | Phone prompt after signup; invalid numbers rejected; checkout blocked | **PARTIAL** | `test_phone_is_normalised_and_unique` proves `+91 98765-43210` → `9876543210`, duplicate → 409 `phone_already_used`, junk → 422 `invalid_phone` (single error code for every bad input). The prompt itself is unit-rendered; the dialog flow needs a browser. |
| C-07 | Address by manual entry, mocked location, map pin; bad pincode blocked | **NOT RUN** (Phase 2) | |
| C-08 | Cart under ₹500 blocked with exact shortfall; ₹500+ proceeds | **NOT RUN** (Phase 2) | Rules and thresholds are already live in `store_settings`. |
| C-09 | COD order: confirmation, stock decrement, notification, email, admin alert, double-click = 1 order | **NOT RUN** (Phase 2) | |
| C-10 | Order page shows items × qty, total, "Deliver in 1 day(s) by <date>", timeline | **NOT RUN** (Phase 2) | |
| C-11 | Admin sets Shipped/Out for delivery/Delivered; customer sees updates | **NOT RUN** (Phase 3) | |
| C-12 | Cancel in Processing only; stock restored | **NOT RUN** (Phase 3) | |
| C-13 | Referral: 10% first order only, ₹20 after delivery, self-referral rejected | **NOT RUN** (Phase 4) | Referral codes (6 chars, `23456789ABCDEFGHJKMNPQRSTUVWXYZ`) are allocated on first login. |
| C-14 | ₹2,000+ creates locked card; unlocks on delivery; server reveal ₹50–100; single use | **NOT RUN** (Phase 4) | |
| C-15 | Wallet applies, cannot exceed total, ledger correct | **NOT RUN** (Phase 4) | |
| C-16 | No credit until approved + received; card removed | **NOT RUN** (Phase 4) | |
| C-17 | Badge at ₹20,000 delivered spend with notification, email, progress bar | **NOT RUN** (Phase 4) | |
| C-18 | Contact page: info, tel link, Maps link, feedback form emails + admin inbox | **NOT RUN** (Phase 5) | Store address, phone and maps URL already come from the database. |
| C-19 | Install banner after signup (Android) and iOS instructions; standalone launch | **NOT RUN** (Phase 7) | Manifest + icons are in place and asserted against the built app. |
| C-20 | Offline shell + browsed catalogue; ordering blocked offline; update prompt after deploy | **PARTIAL** | `NetworkOnly` for `/api/*` and Supabase origins is asserted in `e2e/pwa.spec.ts` against a production build; the offline *catalogue* view needs Phase 2's cache strategy. |
| C-21 | axe: zero critical/serious on Home, Product, Cart, Checkout, Orders | **NOT RUN** (Phase 7) | Home-level a11y is enforced statically by `eslint-plugin-jsx-a11y`. |

## Admin journey

| ID | Scenario | Status | Evidence |
|---|---|---|---|
| A-01 | Non-admin blocked (UI redirect + API 403) | **PASS (API)** | `test_admin_routes_reject_customers` (403 `admin_only`), `test_admin_routes_allow_the_owner` (200), `test_demoting_the_profile_revokes_admin_immediately` — the role is read from `profiles.role` per request, never from the token. `ProtectedRoute` is unit-tested. |
| A-02 | New order raises red dot, in-app alert, email; opening clears it | **NOT RUN** (Phase 3) | |
| A-03 | Orders default to Active; filters/search; detail completeness | **NOT RUN** (Phase 3) | |
| A-04 | Per-order delivery days visible to customer | **NOT RUN** (Phase 3) | |
| A-05 | Every status transition; invalid rejected; events logged | **NOT RUN** (Phase 3) | |
| A-06 | Customer cancellation alerts admin | **NOT RUN** (Phase 3) | |
| A-07 | Inline add on a category row appears on the storefront | **NOT RUN** (Phase 5) | |
| A-08 | Bulk add: valid file commits; bad rows show per-row errors and commit nothing; SSRF URL rejected | **NOT RUN** (Phase 5) | |
| A-09 | Edit product/category/subcategory; delete with products blocked or reassigned | **NOT RUN** (Phase 5) | |
| A-10 | Analytics cards drill down; empty range safe; figures reconcile | **NOT RUN** (Phase 6) | |
| A-11 | Low-stock row opens product edit; saving updates the count | **NOT RUN** (Phase 6) | |
| A-12 | Return approve + mark received credits exactly once | **NOT RUN** (Phase 4) | |
| A-13 | Customers list, tier filter, profile with past orders, top-customer flag | **NOT RUN** (Phase 6) | |
| A-14 | Offer to all / one tier reaches bell, banner, push | **NOT RUN** (Phase 5) | |
| A-15 | Settings changes apply on next checkout without redeploy, audit-logged | **NOT RUN** (Phase 5) | `/api/v1/config` already serves the live `store_settings` row. |
| A-16 | No cart or customer footer in admin; tabs + bottom nav correct on mobile | **PASS (shell)** | `src/App.test.tsx` › "keeps the customer cart out of the admin shell and lazy-loads admin"; `e2e/shell.spec.ts` › "admin has tabs, no customer search and no customer footer". |

## Security

| ID | Scenario | Status | Evidence |
|---|---|---|---|
| S-01 | Anon key gets nothing through Supabase REST; no service key in any bundle | **PASS** | Live probe: RLS enabled on all 7 public tables, **0** table grants to `anon`/`authenticated`. `tests/test_api_db.py::test_public_tables_have_no_anon_access` fails if either ever regresses (it also tries `SET LOCAL ROLE anon` where PostgREST's roles exist). CI greps the built bundle for service-role strings. |
| S-02 | IDOR: no cross-user access on any endpoint | **PARTIAL** | `/api/v1/me` derives the subject from the verified token only (`test_me_requires_a_token`, `test_first_login_creates_a_profile`); order endpoints arrive in Phase 2. |
| S-03 | Client-sent price/total/discount/role/status/user_id ignored or rejected | **NOT RUN** (Phase 2) | `PATCH /api/v1/me` accepts only name and notification preferences; role is not writable anywhere. |
| S-04 | 20 parallel orders for the last unit → exactly one succeeds; replays apply once | **NOT RUN** (Phase 2) | |
| S-05 | Expired/forged/wrong-audience JWT rejected | **PASS** | `tests/test_security_jwt.py`: expired, wrong audience, wrong issuer, HS256 algorithm confusion, `alg: none`, unverified email, unknown key id — each rejected with `unauthenticated`. |
| S-06 | Rate limits trip on checkout, feedback, code guessing, push registration | **NOT RUN** (Phase 1+) | Limiter and Redis store wired; endpoints arrive with their phases. |
| S-07 | XSS/SQLi payloads inert in web and email | **PARTIAL** | No `dangerouslySetInnerHTML` anywhere; every query is parameterised (SQLAlchemy Core/ORM); CI greps. |
| S-08 | Bad uploads rejected (type, size, polyglot, SVG) | **NOT RUN** (Phase 5) | |
| S-09 | Security headers present; securityheaders.com grade A | **PARTIAL** | `tests/test_headers.py`, `tests/test_health.py`, `test_errors.py` assert CSP, frame-ancestors, permissions-policy and HSTS-in-production. Host headers ship in the Vercel/Netlify templates; the grade needs a deployed domain. |
| S-10 | gitleaks, pip-audit, npm audit clean of high/critical | **PASS** | CI Security job green: gitleaks over all history (binary 8.21.2 with the repo config), `pip-audit` → *no known vulnerabilities*, `npm audit` → *0 vulnerabilities*. |
| S-11 | Production: /docs off, no stack traces, CORS allowlist only | **PASS (API)** | `test_docs_hidden_in_production`, `test_wildcard_cors_is_rejected`, and 500s return a generic message. |
| S-12 | Every admin action appears in audit_log | **NOT RUN** (Phase 3) | |

## PWA and performance

| ID | Scenario | Status | Evidence |
|---|---|---|---|
| P-01 | Lighthouse on throttled 4G: installable, Perf ≥ 85, A11y ≥ 95, initial JS ≤ 200 KB gzip, manifest complete | **PARTIAL** | Initial JS **176.8 KB gzip** (budget gate fails the build above 200 KB). `e2e/pwa.spec.ts` asserts name, `MSG`, start_url, scope, theme `#B91C1C`, 192/512/maskable icons, `sw.js` served and `NetworkOnly` for the API — against a production build, not the dev server. Lighthouse needs a deployed URL (Phase 7/8). |

## What must be true before this can be called done

1. Phases 2–8 complete with their scenarios moved to `PASS`.
2. A green CI run linked per scenario, or a recorded local command.
3. Lighthouse and securityheaders.com artefacts captured from staging.
4. The owner-signed privacy policy and terms.
5. A completed restore drill.
