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
| IDs | UUID v4 for rows; order numbers are `TP-000123`. |
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
| 400 | `bad_request`, `pincode_not_serviceable`, `below_minimum_order` |
| 401 | `unauthenticated` |
| 403 | `forbidden` (not an admin, not the owner) |
| 404 | `not_found` |
| 409 | `conflict`, `duplicate_order`, `invalid_transition`, `already_credited` |
| 422 | `validation_error` |
| 429 | `rate_limited` (with `Retry-After`) |
| 500 | `internal_error` (no stack trace in production) |

## Endpoint groups (target surface)

| Group | Endpoints | Phase |
|---|---|---|
| system | `GET /healthz`, `GET /healthz/ready`, `GET /api/v1/status`, `GET /api/v1/config` | 0 ✅ |
| me | `GET/PATCH /me`, `POST /me/phone`, `POST /me/export`, `DELETE /me` | 1 |
| catalogue | `GET /categories`, `GET /brands`, `GET /products`, `GET /products/{slug}` (public read) | 1 |
| cart | `GET/POST/PATCH/DELETE /cart`, `POST /cart/merge` | 2 |
| addresses | `GET/POST/PATCH/DELETE /addresses`, `POST /geo/reverse` (Nominatim proxy) | 2 |
| orders | `POST /orders` (Idempotency-Key), `GET /orders`, `GET /orders/{order_no}`, `POST /orders/{order_no}/cancel`, `POST /orders/{order_no}/returns` | 2–4 |
| wallet & rewards | `GET /wallet`, `GET /rewards`, `POST /rewards/scratch/{id}/reveal`, `POST /referrals/apply` | 4 |
| returns | `GET /returns`, `GET /returns/{id}` | 4 |
| notifications | `GET /notifications`, `POST /notifications/{id}/ack`, `POST /push/subscribe`, `DELETE /push/subscribe` | 3 |
| feedback | `POST /feedback` | 5 |
| admin | `GET /admin/analytics/*`, `GET/PATCH /admin/orders/*`, `GET/POST/PATCH/DELETE /admin/products/*`, `POST /admin/products/bulk/preview`, `POST /admin/products/bulk/commit`, `/admin/categories`, `/admin/brands`, `/admin/customers`, `/admin/offers`, `/admin/settings`, `/admin/feedback`, `/admin/audit` | 3–6 |

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

## Regenerating the typed client

```bash
npm run api:types        # dumps the schema, runs openapi-typescript
```

Consumers import types only:

```ts
import type { PublicConfig, ErrorResponse } from '@tripat/api-client';
```
