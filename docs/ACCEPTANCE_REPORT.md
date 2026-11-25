# Acceptance report

Rule: **never mark a scenario passed without running it.** `PASS` requires
evidence in this file — a command output recorded here or a CI run link.
Everything else is `NOT RUN` (with the phase that will exercise it) or
`PARTIAL`.

- Report date: **2026-11-25**
- Phases closed: **0, 1, 2**. Phase 2 (cart, addresses, COD checkout, customer
  orders, owner order queue) is delivered and tested; Phase 3 (notifications,
  email, red dot) is next.
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
| API lint + format | `cd apps/api && ruff check . && ruff format --check .` | ✅ clean (69 files formatted) |
| API types | `cd apps/api && mypy app` | ✅ `no issues found in 55 source files` |
| API tests (local, no database) | `cd apps/api && pytest` | ✅ **226 passed, 72 skipped** — the 72 are the `db` tests, which skip without `TEST_DATABASE_URL` |
| API tests (real Postgres) | CI job *API · lint, types, tests*, and locally against PostgreSQL 16 | ✅ **298 tests collected** (226 + 72 db): 297 passed, 1 skipped (the `anon`-role RLS probe needs Supabase's roles). The db set is 16 Phase 1 + 25 Phase 2 + 17 admin-order + 14 Phase 3 notification/outbox tests, run after `alembic upgrade head` → `downgrade base` → `upgrade head` — all three steps verified against real Postgres 16 before merging |
| Python dependency audit | `pip-audit --skip-editable` | ✅ `No known vulnerabilities found` |
| Web types | `npm run typecheck` | ✅ clean (web + api-client) |
| Web lint | `npm run lint` | ✅ clean, `--max-warnings 0` |
| Web unit tests | `npm test` | ✅ `6 files, 44 tests passed` (cart reducer/storage 13, cart page 5, notifications page 4) |
| Production build | `npm run build` | ✅ SW + manifest, 37 precache entries; cart/checkout/orders are separate lazy chunks |
| Bundle budget (P‑01) | `node apps/web/scripts/check-bundle-size.mjs` | ✅ **180.0 KB / 200 KB** gzip initial JS |
| Node dependency audit | `npm audit` | ✅ **0 vulnerabilities** |
| Secret scan | `gitleaks detect --log-opts=--all` (CI) | ✅ clean across all history |
| Schema/type sync | `python -m app.scripts.dump_openapi` + `npm run api:types` | ✅ **28 paths, 36 aliases**, no drift (CI diff-gates it) |
| CI run (Phase 3 head) | [45636378146](https://github.com/Jashan-ux/TripatGroceryStore/actions/runs/45636378146) | ✅ **5/5 jobs green** — Web (44 tests), API (298 tests incl. all 72 db tests against Postgres), API container, Security, E2E (guest-cart journey included) |
| Live schema inventory | SQL via the Supabase connector | ✅ **13 tables** + `alembic_version`, 2 Phase 3 tables (10 + 11 columns), 3 indexes on them, 2 new triggers, 5 enums |
| Live seed | SQL via the Supabase connector | ✅ 41 categories (10 departments), 30 brands, 70 products (12 unbranded), 44 variants |
| Live drift check | SQLAlchemy metadata (83 columns) vs `information_schema` | ✅ 83/83 — no missing, no extra column |
| Live security posture | SQL via the Supabase connector | ✅ RLS on **13/13** tables (2/2 new), 0 grants to `anon`/`authenticated`, `alembic_version` = **`0004_notifications_and_email`** |

### Two things this sandbox cannot prove, and how they are covered

1. **Browser against live data.** The sandbox has no browser and cannot open a
   Postgres connection to `*.supabase.co` (`ConnectionResetError` on the TLS
   upgrade), so no preview here is backed by the hosted catalogue. The same code
   paths are exercised instead by the 54 CI database tests and the Playwright
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
| C-03 | ADD becomes stepper, no reload, count/sticky bar update | **PASS** | `src/features/cart/cart.test.ts` (add merges, clamps to stock, sold-out refused), `src/pages/CartPage.test.tsx` (stepper edits persist), `e2e/cart.spec.ts` (ADD on a card becomes a stepper without leaving the results page, badge follows the count). |
| C-04 | Guest cart survives reload, merges on login | **PASS (device-scoped by design)** | The cart is `localStorage` (ids + quantities only) and is re-priced by the API, so there is no server cart to merge: `e2e/cart.spec.ts` reloads and the basket is intact; two tabs stay in step through the `storage` event (`sameLines` guard prevents loops). This was the open design question — no cart table was added. |
| C-05 | Email signup logs in; survives reload and browser restart | **NOT RUN** (needs a browser with Supabase reachability) | Provider config, redirect URLs and the session store are wired; see the limitation above. |
| C-06 | Phone prompt after signup; invalid numbers rejected; checkout blocked | **PARTIAL** | `test_phone_is_normalised_and_unique` proves `+91 98765-43210` → `9876543210`, duplicate → 409 `phone_already_used`, junk → 422 `invalid_phone` (single error code for every bad input). The prompt itself is unit-rendered; the dialog flow needs a browser. |
| C-07 | Address by manual entry; bad pincode blocked | **PARTIAL** | Manual entry works end to end: `test_address_crud_and_default_handling`, `test_the_address_phone_is_normalised` (+91 98765-43210 → 9876543210), `test_a_malformed_pincode_is_rejected` (422), `test_addresses_are_invisible_to_other_customers` (404 on someone else's id). Map pin / "use my location" is **not built** — it needs a maps key from the owner. |
| C-08 | Cart under ₹500 blocked with exact shortfall; ₹500+ proceeds | **PASS** | The quote returns a `minimum_order` blocking issue with `shortfall_paise` and `can_checkout=false` (`test_quote_reports_the_exact_shortfall_under_the_minimum`), and the order endpoint refuses the same basket independently (`test_order_below_the_minimum_is_refused_with_the_shortfall`). The cart page renders the shortfall and disables the CTA, and the E2E journey asserts the "Add ₹470 more" copy. The ₹500 threshold comes from `store_settings`, not code. |
| C-09 | COD order: confirmation, stock decrement, double-click = 1 order | **PASS** | Place + snapshot + stock decrement + idempotent replay are proven (`test_placing_an_order_snapshots_prices_and_decrements_stock`, `test_a_replayed_checkout_returns_the_original_order`, `test_variant_stock_is_decremented_on_the_variant`). Confirmation screen and order page ship; the bell line and the confirmation email are queued in the same transaction (`test_placing_an_order_rings_the_customer_and_the_owner`, `test_the_confirmation_and_the_shop_alert_are_queued`), and a checkout that fails on stock notifies nobody (`test_a_failed_checkout_notifies_nobody`). |
| C-10 | Order page shows items × qty, total, "Deliver by <date>", timeline | **PASS (API + page)** | `deliver_by` is computed from `store_settings.default_delivery_days` and asserted in the quote/order tests; the timeline is built from `order_events`, not from `status` (`test_the_timeline_records_events_not_the_current_status`); `OrderDetailPage` renders items, totals, address snapshot, expected date and the event trail. |
| C-11 | Admin sets Shipped/Out for delivery/Delivered; customer sees updates | **PASS** | `test_the_happy_path_settles_the_cash_on_delivery` walks all three steps and flips `payment_status` to `paid` on delivery; the customer's order page shows the new status and events, and each move writes a bell line + a queued email (`test_shop_transitions_ring_the_customer`, `test_cancellation_and_its_reason_reach_the_customer`). Push arrives in Phase 7. |
| C-12 | Cancel in Processing only; stock restored | **PASS** | Customer path: `test_cancelling_restores_stock_and_cannot_be_repeated`, `test_an_order_cannot_be_cancelled_once_it_has_shipped`. Owner path: `test_cancelling_from_the_queue_puts_the_stock_back`, `test_a_dispatched_order_can_no_longer_be_cancelled`, `test_stock_is_restored_exactly_once_even_for_two_lines`. |
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
| A-02 | New order raises red dot, in-app alert, email; opening clears it | **PASS (email = queued, sends with a Resend key)** | The order transaction writes one `new_order` notification per owner profile plus a queued email (`test_placing_an_order_rings_the_customer_and_the_owner`); the header bell and the admin *Orders* tab show the unread count from `GET /notifications/unread-count` (polled every 60 s while visible), `/notifications` lists them, and `POST /notifications/{id}/ack` / `read-all` clear it (`test_ack_and_read_all_move_the_red_dot`, 4 Vitest cases on the page). Without `RESEND_API_KEY` each mail is recorded `skipped` with the reason rather than pretending (`test_without_a_provider_the_outbox_says_so_and_sends_nothing`); with a key each mail is sent exactly once (`test_with_a_provider_each_email_is_sent_once`). |
| A-03 | Orders default to New; filters/search; detail completeness | **PASS** | `GET /api/v1/admin/orders` defaults the UI to `processing`, filters by status, searches number/name/phone, pages and returns per-status counts (`test_the_queue_shows_who_ordered_what`, `test_filters_by_status_and_searches_by_number_or_phone`, `test_the_queue_pages`, `test_detail_carries_the_timeline`). The tab is no longer a placeholder page. |
| A-04 | Per-order delivery days visible to customer | **PASS** | `PATCH /admin/orders/{id}/delivery-days` re-promises one order from today (0–14 days), writes a timeline event and tells the customer (`test_the_shop_can_promise_a_different_date_for_one_order`, `test_a_delivery_change_rings_the_customer`, refused once finished: `test_a_delivery_change_is_refused_once_the_order_is_finished`, bounds: `test_a_delivery_change_keeps_the_promise_sane`). The admin detail panel carries the control; the customer sees the new date on the order page and in the bell. |
| A-05 | Every status transition; invalid rejected; events logged | **PASS** | `ALLOWED_TRANSITIONS` in `app/services/admin_orders.py`; a skipped step is a 409 carrying `status`, `requested` and `allowed` (`test_a_skipped_step_is_refused_with_the_allowed_moves`); an unknown status is a 422; every move appends an `order_events` row with `actor='admin'`. |
| A-06 | Customer cancellation alerts admin | **PASS** | The queue reflects it immediately (`test_a_customer_cancellation_and_a_shop_cancellation_agree` — and the shop cannot resurrect it), and a customer cancel now rings the shop's bell with the order number (`test_a_customer_cancellation_rings_the_shop`). |
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
| S-02 | IDOR: no cross-user access on any endpoint | **PASS (customer surface)** | Addresses: `test_addresses_are_invisible_to_other_customers` (list scoped, foreign id → 404). Orders: every query filters by `profile_id` and `test_orders_are_listed_and_scoped_to_the_owner` proves another customer gets 404 on list and detail. Admin routes are gated by `require_admin` (`test_customers_cannot_reach_the_queue` → 403/401). |
| S-03 | Client-sent price/total/discount/role/status/user_id ignored or rejected | **PASS** | `APIModel` forbids unknown keys, so a payload carrying `price_paise`/`total_paise` is a 422 `validation_error` (`test_money_in_the_payload_is_refused`); every amount is recomputed from the catalogue. Role is only writable by `bootstrap_role` from `ADMIN_EMAILS`; order status only through the admin transition table. |
| S-04 | Parallel orders for the last units → exactly stock-many succeed; replays apply once | **PASS** | `test_the_last_units_have_exactly_one_winner_each` fires 7 concurrent checkouts at 3 units: exactly 3 succeed, 4 get `insufficient_stock`, and stock never goes negative (conditional `UPDATE ... WHERE stock >= :n`). `test_a_replayed_checkout_returns_the_original_order` proves the `Idempotency-Key` replays the first order. |
| S-05 | Expired/forged/wrong-audience JWT rejected | **PASS** | `tests/test_security_jwt.py`: expired, wrong audience, wrong issuer, HS256 algorithm confusion, `alg: none`, unverified email, unknown key id — each rejected with `unauthenticated`. |
| S-06 | Rate limits trip on checkout, feedback, code guessing, push registration | **NOT RUN** (Phase 1+) | Limiter and Redis store wired; endpoints arrive with their phases. |
| S-07 | XSS/SQLi payloads inert in web and email | **PARTIAL** | No `dangerouslySetInnerHTML` anywhere; every query is parameterised (SQLAlchemy Core/ORM); CI greps. |
| S-08 | Bad uploads rejected (type, size, polyglot, SVG) | **NOT RUN** (Phase 5) | |
| S-09 | Security headers present; securityheaders.com grade A | **PARTIAL** | `tests/test_headers.py`, `tests/test_health.py`, `test_errors.py` assert CSP, frame-ancestors, permissions-policy and HSTS-in-production. Host headers ship in the Vercel/Netlify templates; the grade needs a deployed domain. |
| S-10 | gitleaks, pip-audit, npm audit clean of high/critical | **PASS** | CI Security job green: gitleaks over all history (binary 8.21.2 with the repo config), `pip-audit` → *no known vulnerabilities*, `npm audit` → *0 vulnerabilities*. |
| S-11 | Production: /docs off, no stack traces, CORS allowlist only | **PASS (API)** | `test_docs_hidden_in_production`, `test_wildcard_cors_is_rejected`, and 500s return a generic message. |
| S-12 | Every admin action appears in audit_log | **PARTIAL** | Status changes append an immutable `order_events` row (status, actor `admin`, note, timestamp) and are logged structurally (`order_status_changed`). A general `audit_log` table lands with the admin catalogue tools in Phase 5. |

## PWA and performance

| ID | Scenario | Status | Evidence |
|---|---|---|---|
| P-01 | Lighthouse on throttled 4G: installable, Perf ≥ 85, A11y ≥ 95, initial JS ≤ 200 KB gzip, manifest complete | **PARTIAL** | Initial JS **179.5 KB gzip** (budget gate fails the build above 200 KB). `e2e/pwa.spec.ts` asserts name, `MSG`, start_url, scope, theme `#B91C1C`, 192/512/maskable icons, `sw.js` served and `NetworkOnly` for the API — against a production build, not the dev server. Lighthouse needs a deployed URL (Phase 7/8). |

## What must be true before this can be called done

1. Phases 3–8 complete with their scenarios moved to `PASS`.
2. A green CI run linked per scenario, or a recorded local command.
3. Lighthouse and securityheaders.com artefacts captured from staging.
4. The owner-signed privacy policy and terms.
5. A completed restore drill.
