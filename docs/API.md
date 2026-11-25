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
| 429 | `rate_limited` (with `Retry-After`) |
| 500 | `internal_error` (no stack trace in production) |

## Endpoint groups (target surface)

| Group | Endpoints | Phase |
|---|---|---|
| system | `GET /healthz`, `GET /healthz/ready`, `GET /api/v1/status`, `GET /api/v1/config` | 0 ✅ |
| me | `GET/PATCH /me`, `POST /me/phone`, `POST /me/export`, `DELETE /me` | 1 |
| catalogue | `GET /categories`, `GET /brands`, `GET /products`, `GET /products/{slug}` (public read) | 1 |
| cart | **not built on purpose** — the basket lives on the device; `POST /checkout/quote` prices it | 2 ✅ |
| addresses | `GET /addresses`, `POST /addresses`, `PUT/DELETE /addresses/{id}` | 2 ✅ (map pin in Phase 7) |
| checkout & orders | `POST /checkout/quote` (public), `POST /orders` (`Idempotency-Key`), `GET /orders`, `GET /orders/{id}`, `POST /orders/{id}/cancel` | 2 ✅ (returns in Phase 4) |
| wallet & rewards | `GET /wallet`, `GET /rewards`, `POST /rewards/scratch/{id}/reveal`, `POST /referrals/apply` | 4 |
| returns | `GET /returns`, `GET /returns/{id}` | 4 |
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

## Regenerating the typed client

```bash
npm run api:types        # dumps the schema, runs openapi-typescript
```

Consumers import types only:

```ts
import type { PublicConfig, ErrorResponse } from '@tripat/api-client';
```
