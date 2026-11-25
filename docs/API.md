# API

Base path: `/api/v1`. Probes live at the root (`/healthz`, `/healthz/ready`) so a
platform can check the container without auth.

- **Interactive docs**: `/docs` (Swagger) and `/redoc` — **disabled when
  `ENVIRONMENT=production`**; `/openapi.json` is also off there.
- **Generated types**: `packages/api-client` — regenerate with `npm run api:types`.
  CI fails if the committed schema drifts from the code.

## Conventions

| Topic | Rule |
|---|---|
| Money | integer **paise** (`bigint`). `₹500.00` ⇄ `50000`. No floats anywhere. |
| Time | ISO-8601 with `Z`, always UTC. The UI renders in `Asia/Kolkata`. |
| IDs | UUID v4 for rows; order numbers are `MSG-YYMMDD-XXXXX` (5 random chars, unique per day). |
| Pagination | `?page=1&page_size=20` → `{items: [...], pagination: {page, page_size, total, total_pages}}`. `page_size` max 100. |
| Filtering | explicit query params (`category`, `brand`, `min_price_paise`, `max_price_paise`, `tags`, `in_stock`, `sort`, `q`). |
| Idempotency | `Idempotency-Key: <uuid>` **required** on `POST /orders`; also used on every credit (returns, referral payout). Replaying returns the original result, never a duplicate. |
| Auth | `Authorization: Bearer <supabase access token>`. Verified against JWKS (`iss`, `aud`, `exp`) on every protected route; role read from `profiles.role`. |
| Errors | one shape, see below. |
| Caching | `Cache-Control: no-store` on all `/api/*`. |

### Error shape

```json
{
  "error": {
    "code": "insufficient_stock",
    "message": "Only 3 left of Tata Tea Gold 1kg.",
    "details": { "product_id": "…", "available": 3 },
    "request_id": "7f3c…"
  }
}
```

`code` is stable and machine-readable; `message` is safe to display. Validation
failures return `code: "validation_error"` with
`details.fields: [{field, message, type}]`.

| Status | code examples |
|---|---|
| 400 | `bad_request` |
| 401 | `unauthenticated` |
| 403 | `admin_only`, `forbidden` (not an admin, not the owner) |
| 404 | `not_found`, `order_not_found`, `address_not_found` |
| 409 | `insufficient_stock`, `minimum_order_not_met`*, `phone_required`, `order_not_cancellable`, `invalid_status_transition`, `already_credited` |
| 422 | `validation_error` |
| 429 | `rate_limited` (with `Retry-After`; `details` = `{scope, limit, retry_after_seconds, window_seconds}`) |
| 500 | `internal_error` (no stack trace in production) |

## Endpoint groups (target surface)

| Group | Endpoints | Phase |
|---|---|---|
| system | `GET /healthz`, `GET /healthz/ready`, `GET /api/v1/status`, `GET /api/v1/config` | 0 ✅ |
| me | `GET/PATCH /me`, `POST /me/phone`, `POST /me/export`, `DELETE /me` | 1 |
| catalogue | `GET /categories`, `GET /brands`, `GET /products`, `GET /products/{slug}` (public read) | 1 |
| cart | **not built on purpose** — the basket lives on the device; `POST /checkout/quote` prices it | 2 ✅ |
| addresses | `GET /addresses`, `POST /addresses`, `PUT/DELETE /addresses/{id}` | 2 ✅ (map pin in Phase 7) |
| checkout & orders | `POST /checkout/quote` (public), `POST /orders` (`Idempotency-Key`), `GET /orders`, `GET /orders/{id}`, `POST /orders/{id}/cancel`, `POST /orders/{id}/return` | 2 ✅ + 4 ✅ |
| wallet & rewards | `GET /rewards`, `GET /rewards/wallet`, `POST /rewards/referral`, `GET /rewards/scratch-cards`, `POST /rewards/scratch-cards/{id}/reveal` | 4 ✅ |
| returns | `GET /returns`, `POST /orders/{id}/return`; admin: `GET /admin/returns`, `POST /admin/returns/{id}/decision`, `POST /admin/returns/{id}/received` | 4 ✅ |
| notifications | `GET /notifications`, `POST /notifications/{id}/ack`, `POST /push/subscribe`, `DELETE /push/subscribe` | 3 |
| feedback | `POST /feedback` | 5 |
| admin | `GET /admin/whoami` ✅, `GET /admin/orders`, `GET /admin/orders/{id}`, `POST /admin/orders/{id}/status` ✅; products/categories/brands/customers/offers/settings/analytics/audit | 3–6 |

Every admin route sits behind **one** dependency (`require_admin`) and is the only
place admin code exists on the server.

## Phase 0 — live endpoints

```bash
curl -s http://localhost:8000/healthz | jq
{
  "status": "ok",
  "version": "0.1.0",
  "environment": "local",
  "uptime_seconds": 12.4,
  "components": [
    { "name": "api", "status": "ok" },
    { "name": "database", "status": "ok", "latency_ms": 3.1 }
  ]
}

curl -s http://localhost:8000/api/v1/config | jq
{
  "environment": "local",
  "store_name": "Tripat Pansari MSG Store",
  "store_phone": "+91 87089-73386",
  "store_address": "Tripat Pansari MSG Store, near Sabji Mandi, opposite Gyani Achhar Bhandaar, Mandi Dabwali, 125104",
  "store_maps_url": "",
  "feedback_email": "tripatinsan029@gmail.com",
  "phone_otp_enabled": false,
  "turnstile_enabled": false,
  "supabase_url": "",
  "supabase_anon_key": "",
  "vapid_public_key": ""
}
```

`/api/v1/config` is intentionally public and excludes the service-role key,
database URL and every other secret (tested:
`apps/api/tests/test_health.py::test_public_config_exposes_store_contact_but_no_secrets`).

## Phase 2 — cart, checkout and orders

The client never sends money. A quote or an order carries **ids and quantities**;
every price, total and availability flag is computed from the catalogue. A payload
that includes `price_paise`, `total_paise` or any other money key is rejected with
`422 validation_error` (`APIModel` forbids unknown keys).

```bash
# Price a basket (public — works for a guest who has not signed in)
curl -s -X POST http://localhost:8000/api/v1/checkout/quote \
  -H 'Content-Type: application/json' \
  -d '{"items":[{"product_id":"<uuid>","variant_id":null,"quantity":2}],"pincode":"125104"}' | jq
{
  "lines": [
    { "product_id": "…", "name": "Palak", "unit_price_paise": 3000,
      "line_total_paise": 6000, "available_stock": 12, "issue": null }
  ],
  "subtotal_paise": 6000, "delivery_fee_paise": 0, "discount_paise": 0,
  "total_paise": 6000, "item_count": 2,
  "minimum_order_paise": 50000, "shortfall_paise": 44000,
  "deliver_by": "2026-11-26", "pincode_serviceable": true,
  "blocking_issues": [
    { "code": "minimum_order", "message": "Add ₹440 more to reach the ₹500 minimum order." }
  ],
  "can_checkout": false
}
```

`blocking_issues[].code` ∈ `empty_cart | minimum_order | pincode | stock`.
`lines[].issue` ∈ `out_of_stock | partially_available | unavailable` (null when
fine). The UI shows the message verbatim and disables the CTA while any issue is
present — the same rules are enforced again by `POST /orders`.

```bash
# Place the order (auth required; the key makes replays free)
curl -s -X POST http://localhost:8000/api/v1/orders \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{"address_id":"<uuid>","items":[{"product_id":"<uuid>","variant_id":null,"quantity":2}],
       "customer_note":"Ring twice"}'
```

`201` returns the order with `order_number`, `status: "processing"`,
`payment_method: "cod"`, `payment_status: "pending"`, a **snapshot** of the address
and of every line's name/price, `deliver_by`, `items[]` and `events[]`. Replaying
the same `Idempotency-Key` returns the original order — never a second one — and
`GET /orders/{id}` is scoped to the caller, so anyone else's id is a `404`.

| Rule | Behaviour |
|---|---|
| Minimum order | `minimum_order_not_met` (`422`) with `details.shortfall_paise`; the quote reports it first. |
| Pincode | `pincode_not_serviceable` (`422`); serviceable pincodes come from `store_settings`. |
| Phone | `phone_required` (`409`) — the delivery partner has to be able to call. |
| Stock | `insufficient_stock` (`409`) with `details.items`. Stock is taken with `UPDATE … WHERE stock >= :n`, so concurrent checkouts cannot oversell. |
| Cancel | Only while `processing`; restores stock, writes an event. After dispatch: `409 order_not_cancellable`. |

Admin side (all behind `require_admin`):

| Route | Purpose |
|---|---|
| `GET /admin/orders?status=&q=&page=&page_size=` | The queue: newest first, per-status `counts` for the tabs. |
| `GET /admin/orders/{id}` | Full order, address snapshot and event trail. |
| `PATCH /admin/orders/{id}/delivery-days` | `{"days": 0..14, "note": "…"}` — re-promises *this* order from today. Writes a timeline event, rings the customer's bell (`system` kind) and queues the email; money, stock and status do not move. `409 order_not_editable` once the order is `delivered`, `cancelled` or `returned`; out-of-range days is `422`. |
| `POST /admin/orders/{id}/status` | `{"status": "shipped", "note": "…"}`. Allowed moves: `processing → shipped | cancelled`, `shipped → out_for_delivery`, `out_for_delivery → delivered`, `delivered → returned`. Anything else is `409 invalid_status_transition` with `details.allowed`. Cancelling restores stock; `delivered` settles the COD payment. |

## Phase 3 — notifications and the email outbox

Both sides of the shop get told what happened, without a push service.

| Route | Purpose |
|---|---|
| `GET /notifications?page=&page_size=1..50` | Newest first. Returns `items[]` (`id, kind, title, body, href, order_id, read, created_at`), plus `unread_count`, `total`, `page`, `page_size`, `total_pages`. |
| `GET /notifications/unread-count` | `{"unread_count": n}` — the red dot. Polled every 60 s while the tab is visible. |
| `POST /notifications/{id}/ack` | Marks one read. Idempotent; another profile's id is `404 notification_not_found`, never `403`. |
| `POST /notifications/read-all` | `{"marked": n}` — 0 when there is nothing unread. |

All four require a bearer token (`401` otherwise) and only ever see their own rows.

**What is written, and when.** Notifications are inserted **inside the order
transaction**, so a checkout that fails on stock (or any other 409/500) notifies
nobody. Kinds and copy:

| Trigger | Recipient | Kind | `href` |
|---|---|---|---|
| Customer places an order | customer | `order_placed` — "Order MSG-… confirmed" + items/total/COD line | `/orders/{id}` |
| Same order | every profile in `ADMIN_EMAILS` | `new_order` — "New order MSG-…" + name, phone, items, total | `/admin/orders` |
| Status move by the shop, or a customer cancel | customer | `order_status` — "MSG-…: Packed and shipped" / `order_cancelled` with the reason as `body` | `/orders/{id}` |
| Customer cancels | every owner profile | `order_cancelled` — "MSG-… cancelled by the customer" + "the stock is back on the shelf" | `/admin/orders` |
| Shop changes the delivery promise | customer | `system` — "MSG-…: Delivery in 3 days" | `/orders/{id}` |

**Email.** `email_messages` is an outbox, not a mail call inline with the request:
a row is queued in the same transaction, and a background task flushes it with its
own session after the response is committed. `dedupe_key` (`order:{id}:placed`,
`order:{id}:new:{email}`, `order:{id}:status-{status}:{email}`) makes a replay
harmless; the unique index is the backstop.

| Situation | Row status | `last_error` |
|---|---|---|
| `RESEND_API_KEY` empty | `skipped` | `No email provider configured (RESEND_API_KEY is empty)` |
| Resend returns 200/201/202 | `sent`, `sent_at` set | — |
| Resend errors, times out or returns 4xx/5xx | `failed` | `HTTP 500: …` / `ConnectError: …` |

Nothing is retried automatically — a `failed` row stays put with its `attempts`
count so the reason is visible, and `skipped` means "queued but no provider", which
is the correct state for a shop that has not set up Resend yet. Mail never breaks a
request: the flush is wrapped and logged.

## Phase 4 — wallet, referrals, scratch cards, returns, badges

Money is integer paise everywhere, and every credit is a row in `wallet_entries`
with the balance it produced. `wallets.balance_paise` is kept equal to the sum of
its entries, and the three credits that could fire twice (referral, card, refund)
store the ledger entry they made in a **unique** column — the database refuses a
second credit even if a service check were wrong.

### Customer routes (all need a bearer token; none takes a profile id)

| Route | Purpose |
|---|---|
| `GET /rewards` | The hub in one call: `wallet` (balance + statement), `referrals` (code, share link, friend list, the code *you* joined with), `scratch` (cards + `ready`/`locked`/`revealed` counts), `tier` (`tier`, `spend_paise`, `next_tier`, `next_tier_at_paise`, `remaining_paise`, `progress_pct`). |
| `GET /rewards/wallet?page=&page_size=` | Balance and the paged statement (`delta_paise`, `reason`, `note`, `order_id`, `created_at`). |
| `POST /rewards/referral` | `{"code": "ABCDEF"}` — joins a friend's programme. `409 self_referral`, `409 referral_already_joined`, `409 referral_after_first_order`, `404 referral_code_not_found`. The 10 % discount lands on the **first** order only. |
| `GET /rewards/scratch-cards` | Cards newest first. `amount_paise` is `null` until revealed — the prize exists server-side and is not sent early. |
| `POST /rewards/scratch-cards/{id}/reveal` | Unlocks, credits and returns `{card, credited_paise, wallet_balance_paise}`. `409 scratch_card_locked` before delivery, `409 scratch_card_used` on a second reveal, `409 scratch_card_expired` past the window, `404` for someone else's card. |
| `POST /orders/{id}/return` | `{"items": [{"order_item_id", "quantity"}], "reason": "…"}`. `409 return_order_not_delivered`, `409 return_window_closed`, `409 return_already_open`, `409 return_quantity_too_high`, `404` for another customer's order. |
| `GET /returns` | My returns, newest first, with items and status. |

**Wallet at checkout.** `POST /checkout/quote` and `POST /orders` take
`use_wallet_paise` (default `0`). The server clamps it to the balance **and** to
what is payable, fills `wallet_applied_paise`, `payable_before_wallet_paise` and
`discount_reason`, and sets `payment_status='paid'` when the cash due is zero. The
web asks the quote for the balance first, then re-quotes with the chosen amount;
switching it rotates the idempotency key so a replay cannot silently change what
was paid.

### Admin routes (behind `require_admin`)

| Route | Purpose |
|---|---|
| `GET /admin/returns?status=&page=&page_size=` | The queue with customer name/phone, items and `refund_paise`. Statuses: `requested`, `approved`, `rejected`, `received_credited`. |
| `POST /admin/returns/{id}/decision` | `{"approve": true, "note": "…"}` — decides only. **No money moves.** `409 return_already_decided` on a second decision. |
| `POST /admin/returns/{id}/received` | The goods are back: restores stock, credits the wallet **once** and parks the return in `received_credited`. `409 return_not_approved` if it was never approved; a repeat call is idempotent, not a second credit. |

### Rules that live in settings, not code

| Setting | Default | Effect |
|---|---|---|
| `referral_reward_paise` | 2000 | Paid to the referrer, on delivery of the friend's first order. |
| `referral_discount_pct` | 10 | The friend's first-order discount. |
| `scratch_card_threshold_paise` | 200000 | Basket size that earns a card (at placement; unlocked at delivery). |
| `scratch_card_min_paise` / `_max_paise` | 5000 / 10000 | The reveal range the server draws from. |
| `scratch_card_expiry_days` | 30 | How long an unlocked card can be scratched. |
| `return_window_days` | 3 | How long after delivery a return can be asked for. |
| `tier_gold_paise` / `tier_platinum_paise` / `tier_diamond_paise` | 2000000 / 5000000 / 10000000 | Delivered spend (net of returns) for each badge. |

## Phase 5 — catalogue tools, offers, settings, feedback

Everything the owner does to the shop now goes through the API, so it can be
tested, audited and later moved without rewriting a screen. Two rules shape the
whole group:

* **Every mutation writes exactly one `audit_log` row** (`actor_email`, `action`,
  `entity`, `before`, `after`) inside the same transaction. If the change rolls
  back, so does its audit row.
* **Money is integer paise and prices are validated as a pair** — `price <= mrp`
  is checked against the *stored* MRP even when the request only sends a price,
  so a partial edit cannot create an impossible product.

### Catalogue (behind `require_admin`)

| Route | Purpose |
|---|---|
| `GET /admin/catalogue/products?q=&category_id=&low_stock=&page=&page_size=` | The catalogue as the owner sees it: `available_stock` (sum of active variants when there are any), `low_stock_threshold`, `is_active`, brand and category names. |
| `POST /admin/catalogue/products` | Create. Slug is generated and made unique (`ghee-1-l`, `ghee-1-l-2`); `search_text` is recomputed so search finds it immediately. `422 mrp_below_price`, `404 category_not_found`, `422 duplicate_variant_label`. |
| `PATCH /admin/catalogue/products/{id}` | Partial update from `model_fields_set`. Variants are **replaced wholesale** (an omitted pack disappears), which is why the old rows are deleted before the new ones are inserted. |
| `DELETE /admin/catalogue/products/{id}` | `{outcome}` is `deleted`, or `deactivated` when past order lines reference it — the order history keeps its item names either way. |
| `POST /admin/catalogue/products/bulk` | `{csv, dry_run}`. Required columns `name,category,price`; optional `unit,mrp,stock,brand,image_url`. **All-or-nothing**: every row is validated, and if any row fails nothing is written (`committed=false`, per-row `{line, status, errors}`). Caps at 500 rows; `bulk_bad_header`, `bulk_empty_file`, `bulk_too_many_rows`. `image_url` must be public `https` (SSRF guard). |
| `POST /admin/catalogue/images` | `multipart/form-data` photo. Validated, re-encoded to a 1600 px WebP and stored; returns `{url, width, height, bytes, content_type}`. `422 image_too_large` / `image_type_not_allowed` / `image_unreadable` / `image_dimensions_too_large`, `503 image_upload_unavailable` when storage is not configured. |
| `GET/POST/PATCH/DELETE /admin/catalogue/categories…` | One level of nesting only (`422 category_too_deep`, `422 category_self_parent`). `DELETE` refuses a shelf that still holds anything (`409 category_not_empty`) unless `?reassign_to=<id>` is passed, which moves its products and children and then deletes it. |
| `GET/POST/PATCH/DELETE /admin/catalogue/brands…` | `409 brand_exists` on a duplicate name; `409 brand_in_use` while products point at it. |

### Offers

| Route | Purpose |
|---|---|
| `GET /offers/current` (public) | The newest live offer for the storefront banner, or `{offer: null}`. |
| `POST /admin/offers` | `{title, body, href, audience: all\|gold\|platinum\|diamond, expires_at}`. Creates one `offer` notification per matching **customer** (never an owner) and one queued email each, then records what actually happened in `recipients` and `emails_queued`. `href` must be a path inside this app (`422` otherwise). |
| `GET /admin/offers` | History, newest first, with those counts. |

### Settings

| Route | Purpose |
|---|---|
| `GET /admin/settings` | Every number the shop runs on, in one row. |
| `PATCH /admin/settings` | Only the fields sent are applied. Validated **as a set** (`gifts`: `gold < platinum < diamond`, `scratch_min <= scratch_max`, email shape, `https` Maps URL) → `422 invalid_settings`, nothing half-applied. Clears the 30-second settings cache, so the next checkout uses the new numbers, and writes `settings.updated` with `before`/`after`. |

### Feedback and the audit trail

| Route | Purpose |
|---|---|
| `POST /feedback` (public, optionally signed in) | `{name, phone, email, kind, message}`. Stored first, then one `system` bell line per owner (`href=/admin/feedback`) and one queued email to `store_settings.feedback_email` (`dedupe_key=feedback:{id}`). A missing mail provider never loses the message. |
| `GET /admin/feedback?status=new\|read` | The inbox, newest first. |
| `POST /admin/feedback/{id}/read` | Marks one read (idempotent). |
| `GET /admin/audit?entity=&page=` | `actor_email`, `action`, `entity`, `entity_id`, `summary`, `before`, `after`, `note`, `created_at` — newest first. |

## Rate limits — what a client sees

Every limited route answers the same way, so a client can throttle itself instead
of discovering the ceiling by hitting it:

```
200/201  X-RateLimit-Limit: 5      X-RateLimit-Remaining: 3      X-RateLimit-Reset: 1764118800
429      Retry-After: 1830
         {"error": {"code": "rate_limited",
                    "message": "That's 5 in this window — please try again in 31 minutes.",
                    "details": {"scope": "feedback", "limit": 5,
                                "retry_after_seconds": 1830, "window_seconds": 3600},
                    "request_id": "…"}}
```

Windows are clock-aligned and shared by every worker, so `X-RateLimit-Reset` is a
real timestamp, not an estimate. **Failed attempts count**: a wrong referral code
ends in `404 referral_code_not_found` *and* spends a guess. A refusal happens
before the handler runs, so a limited request never writes anything.

| Route | Key | Default |
|---|---|---|
| `POST /orders` | customer | 10 / hour |
| `POST /checkout/quote` | address | 240 / hour |
| `POST /feedback` | address | 5 / hour |
| `POST /rewards/referral` | customer | 10 / hour |
| `POST /rewards/scratch-cards/{id}/reveal` | customer | 30 / hour |
| `POST /admin/catalogue/images` | admin | 60 / hour |

Tuning is configuration, not a deploy: `RATE_LIMIT_*` (see `.env.example`), `0`
per route to switch one off, `RATE_LIMIT_ENABLED=false` for all of them. The
counters live in Postgres (`rate_limit_counters`, migration `0007`) — there is no
Redis to run.

## Regenerating the typed client

```bash
npm run api:types        # dumps the schema, runs openapi-typescript
```

Consumers import types only:

```ts
import type { PublicConfig, ErrorResponse } from '@tripat/api-client';
```
