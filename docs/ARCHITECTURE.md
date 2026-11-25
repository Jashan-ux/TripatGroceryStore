# Architecture

## Shape

```
Browser (360px Android, 4G)
   │  HTTPS, same origin
   ▼
Vercel / Netlify ── static PWA (React 18, Vite, Workbox)
   │  rewrite /api/* → backend origin
   ▼
FastAPI container (Render / Fly / Railway, always on)
   │  routers → services → repositories
   ├── Supabase Postgres (transaction pooler, asyncpg)
   ├── Supabase Auth (JWT verification via JWKS)
   ├── Supabase Storage (bucket `catalog`, public read / backend-only write)
   ├── (rate limits are rows in the same Postgres — no cache service)
   ├── Resend (transactional email)
   └── Web Push (VAPID)
```

The browser sees **one origin**: it calls `/api/v1/*`, the host rewrites to the
backend, so no CORS is needed in production and cookies/credentials stay simple.
CORS exists only for local development and previews, as an explicit allowlist.

## Layers (backend)

| Layer | Responsibility | Rule |
|---|---|---|
| `app/api/v1/endpoints/*` | HTTP parsing, auth dependencies, status codes | no business rules |
| `app/services/*` | **All** business rules (pricing, gates, wallet, referrals, stock, returns) | unit-tested, transaction-aware |
| `app/repositories/*` | SQLAlchemy queries | parameterised only; ownership in the `WHERE` |
| `app/models/*` | ORM tables, constraints | DB constraints back up every rule |
| `app/core/*` | config, errors, logging, middleware, security | framework glue |
| `app/schemas/*` | Pydantic v2 request/response models | strict, bounded, `extra="forbid"` |

Business rules live **only** in services. Routers never compute a total; the
frontend never computes a total that is trusted.

## Request flow (protected write, e.g. place order)

```mermaid
sequenceDiagram
  participant U as Customer (PWA)
  participant V as Vercel (rewrite)
  participant A as FastAPI
  participant R as Redis
  participant D as Postgres

  U->>V: POST /api/v1/orders (Bearer JWT, Idempotency-Key)
  V->>A: POST /api/v1/orders
  A->>R: rate limit check (user id, else IP)
  A->>A: verify JWT (JWKS, iss, aud, exp)
  A->>D: load profile (role from profiles.role)
  A->>A: service: gate checks (phone, pincode, minimum)
  A->>D: BEGIN; SELECT … FOR UPDATE (product rows)
  A->>D: recompute totals from DB prices, debit wallet, allocate order_no
  A->>D: INSERT order, items, events, wallet ledger, notifications
  A->>D: COMMIT
  A-->>U: 201 + order (idempotency key replay returns the same order)
  A-)U: notification bell + optional push/email
```

## Data model

Money is integer paise (`BIGINT`). Timestamps are `timestamptz` (UTC). Primary
keys are UUIDs except human order numbers (`TP-000123` from a sequence). Every
table has `created_at` and `updated_at` (trigger-maintained).

```mermaid
erDiagram
  profiles ||--o{ addresses : has
  profiles ||--o{ orders : places
  profiles ||--o| carts : owns
  profiles ||--o{ wallet_ledger : "credited/debited"
  profiles ||--o{ referrals : referrer
  profiles ||--o{ scratch_cards : earns
  profiles ||--o{ notifications : receives
  profiles ||--o{ push_subscriptions : registers
  profiles ||--o{ feedback : writes
  profiles ||--o{ return_requests : raises

  brands ||--o{ products : "brands the"
  categories ||--o{ categories : parent
  categories ||--o{ products : groups
  products ||--o{ product_variants : "sold as"
  products ||--o{ cart_items : "in"
  products ||--o{ order_items : "snapshot of"

  carts ||--o{ cart_items : contains
  orders ||--o{ order_items : contains
  orders ||--o{ order_events : "status history"
  orders ||--o| scratch_cards : earns
  orders ||--o{ return_requests : "may have"
  return_requests ||--o{ return_items : contains
  return_items }o--|| order_items : references
  scratch_cards }o--o| orders : "used on"

  store_settings {
    uuid id PK
    bigint minimum_order_paise
    text[] serviceable_pincodes
    int default_delivery_days
    int referral_referrer_reward_paise
    int referral_friend_discount_pct
    bigint scratch_threshold_paise
    int scratch_min_paise
    int scratch_max_paise
    int scratch_expiry_days
    int return_window_days
    bigint tier_gold_paise
    bigint tier_platinum_paise
    bigint tier_diamond_paise
    text notification_email
    text store_phone
    text store_address
    text store_maps_url
  }

  profiles {
    uuid id PK
    text name
    citext email UK
    text phone UK
    enum role "customer|admin|delivery"
    text referral_code UK
    uuid referred_by FK
    bigint lifetime_spend_paise
    enum loyalty_tier "none|gold|platinum|diamond"
    jsonb notification_prefs
  }

  addresses {
    uuid id PK
    uuid user_id FK
    text label
    text name
    text phone
    text line1
    text landmark
    text area
    text city
    text pincode
    numeric lat
    numeric lng
    bool is_default
  }

  products {
    uuid id PK
    text name
    text slug UK
    text description
    uuid brand_id FK
    uuid category_id FK
    bigint mrp_paise
    bigint price_paise
    text unit_label
    int stock
    int low_stock_threshold
    text[] images
    text[] tags
    numeric rating
    bool is_active
  }

  product_variants {
    uuid id PK
    uuid product_id FK
    text label "100g|250g|500g|1kg"
    bigint mrp_paise
    bigint price_paise
    int stock
  }

  cart_items {
    uuid id PK
    uuid cart_id FK
    uuid product_id FK
    uuid variant_id FK
    int qty "CHECK qty > 0"
  }

  orders {
    uuid id PK
    text order_no UK "TP-000123"
    uuid user_id FK
    enum status "processing|shipped|out_for_delivery|delivered|cancelled|returned"
    enum payment_method "cod"
    enum payment_status "pending|paid"
    bigint subtotal_paise
    bigint referral_discount_paise
    bigint coupon_discount_paise
    bigint wallet_used_paise
    bigint total_paise
    int delivery_days
    date expected_delivery_date
    jsonb address_snapshot
    jsonb contact_snapshot
    text idempotency_key UK
    timestamptz placed_at
    timestamptz delivered_at
    timestamptz cancelled_at
  }

  order_items {
    uuid id PK
    uuid order_id FK
    uuid product_id FK
    text name_snapshot
    text image_snapshot
    text unit_snapshot
    bigint price_paise
    int qty
  }

  wallet_ledger {
    uuid id PK
    uuid user_id FK
    bigint delta_paise
    text reason
    text ref
    bigint balance_after_paise "CHECK balance >= 0"
  }

  referrals {
    uuid id PK
    uuid referrer_id FK
    uuid referred_id FK, UK
    enum status
    bigint reward_paise
  }

  scratch_cards {
    uuid id PK
    uuid user_id FK
    uuid order_id FK, UK
    enum status "locked|ready|revealed|used|void"
    bigint amount_paise
    timestamptz expires_at
    uuid used_order_id FK
  }

  return_requests {
    uuid id PK
    uuid order_id FK
    uuid user_id FK
    enum status "requested|approved|rejected|received_credited"
    text reason
  }

  notifications {
    uuid id PK
    uuid user_id FK
    text kind
    text title
    text body
    bool is_read
    timestamptz acknowledged_at
  }

  push_subscriptions {
    uuid id PK
    uuid user_id FK
    text endpoint UK
    text p256dh
    text auth
  }

  offers {
    uuid id PK
    text title
    text body
    enum audience "all|gold|platinum|diamond"
    timestamptz published_at
  }

  feedback {
    uuid id PK
    uuid user_id FK
    text subject
    text message
    text status
  }

  audit_log {
    uuid id PK
    uuid actor_id FK
    text action
    text entity
    jsonb before
    jsonb after
    inet ip
  }
```

## Frontend structure

```
apps/web/src
├── components/layout   AppShell, SiteHeader, BottomNav, SiteFooter
├── components/ui       Button, Card, Skeleton, Badge, Input (Radix/CVA)
├── components/common   ErrorBoundary, EmptyState, OfflineBanner, UpdatePrompt, BrandMark
├── pages               HomePage, SearchPage, ComingSoonPage, NotFoundPage
├── admin/*             lazily-loaded admin bundle (own shell + routes)
├── hooks               useStoreConfig, useOnlineStatus, useServiceWorkerUpdate, usePageTitle
├── i18n                en.ts dictionary + translate() (Hindi-ready)
├── lib                 api.ts (typed fetch), queryClient.ts, serviceWorker.ts, utils.ts
└── styles/globals.css  design tokens (brand red, radii, elevation, safe areas)
```

Route-level code splitting keeps the admin bundle out of the customer payload;
`scripts/check-bundle-size.mjs` fails CI if the initial JS passes 200 KB gzip.

## Key trade-offs

- **Server-rendered nothing.** A Vite SPA behind a static host keeps the whole
  stack simple and cheap; the PWA shell is precached, so repeat visits are fast
  even on 4G. The cost is an empty first paint and reliance on the service worker
  for offline — mitigated with skeletons and honest empty states.
- **No client-side money maths.** Every number is recomputed server-side inside a
  transaction with row locks. The client renders what the server returns.
- **Postgres as the only queue.** Notifications/email/push are written in the same
  transaction as the state change and dispatched afterwards; failures are logged
  and retried by a periodic sweep rather than a broker.
- **One error shape everywhere.** Frontend code maps `code` to copy; no string
  matching on messages.
