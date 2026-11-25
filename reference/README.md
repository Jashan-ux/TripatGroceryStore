# Reference material

`Tripat-Msgstore-site-capture.pdf` — the captured Base44 build (32 pages, printed
2026-11-25) that this project rebuilds from scratch. It is the visual and flow
reference: header shape, catalog rows, admin tabs, orders list, customers,
analytics, settings, referrals and rewards.

## What we take from it

- Storefront layout: red brand banner, category rails with "See all", product
  cards with rating / price / ADD, footer groups (Shop, Customer Service, Account).
- Admin layout: top tab strip (Analytics, Orders, Products, Customers, Offers,
  Categories, Settings) and the mobile bottom nav (Insights, Orders, Products,
  Customers, Settings).
- Copy that is genuinely the shop's: "Your family deserves the best. Choose MSG.",
  "MSG Store · fresh groceries and daily essentials delivered to your doorstep",
  the reward tiers (Gold ₹20,000 / Platinum ₹50,000 / Diamond ₹1,00,000), scratch
  card range ₹50–₹100 for orders above ₹2,000, referral ₹20 + 10%.

## What we deliberately do **not** copy (defects, brief §6.4)

| Defect in the capture                                  | Fix in this build                                                                                               |
| ------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------- |
| Bottom nav / sticky bar overlapping content and footer | Spacing contract: `.pb-nav-safe` / `.pb-combined-safe` + `--bottom-nav-height`, asserted in `e2e/shell.spec.ts` |
| Customer footer and product search inside admin pages  | Admin shell has neither; asserted in unit + E2E tests                                                           |
| Different products sharing one placeholder image       | No mock products ship; category icons allow emoji **or** image                                                  |
| Leftover `MOCK_PAY` labels                             | COD only: `payment_method=cod`, `payment_status=pending/paid`                                                   |
| Placeholder emails like `owner@example.com`            | Real contact (`tripatinsan029@gmail.com`) seeded into `store_settings`; CI greps for `owner@example.com`        |
| Lifetime-spend logic disagreeing with the badge text   | One server-side calculation: delivered totals net of returns; badge copy derived from the same number           |
| Service worker serving stale builds                    | `registerType: 'prompt'` + `index.html` `no-cache` + explicit "update available" prompt                         |
| Emoji-only category icons                              | `categories.emoji` nullable + `image_url`; UI supports both                                                     |

## Requirements history

The Base44 chat is summarised by the brief itself. Later decisions that override
the captures: WhatsApp ordering removed, mock payment gateway removed, mobile OTP
removed (kept behind `PHONE_OTP_ENABLED=false` with a provider interface).
