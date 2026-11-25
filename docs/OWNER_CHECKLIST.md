# Owner-only checklist

Everything below needs **your** accounts, money or identity. I never invent
credentials and never create accounts on your behalf. Tick a line, send me the
env values (or paste them into the host's secret store), and I wire it up.

Legend: ☐ to do · 🔑 needs a secret/env value from you · 🕒 can be done in
parallel with development.

## 0. Two one-minute actions that unblock hosted checks

Both are needed before the hosted database can be verified from CI (the
workflow `DB ops · Supabase` uses them):

- ☐ 🔑 **Actions secret `SUPABASE_DB_URL`** — Settings → Secrets and variables →
  Actions → *Secrets* → New repository secret. Value: the **direct** connection
  string (port 5432, `postgresql+asyncpg://postgres.<ref>:<password>@...`). An
  access token with admin rights is required to write secrets; the agent's token
  can set variables but not secrets (GitHub returns 403).
- ☐ 🔑 **Actions variable `ADMIN_EMAILS`** — same screen, *Variables* tab.
  Value: comma-separated owner addresses, e.g.
  `tripatinsan029@gmail.com,jashaninsan777@gmail.com`.

Once they exist, run **Actions → DB ops · Supabase → Run workflow → verify**.
It prints the connection target, `alembic current`, the drift check and the
inventory (rows per table, RLS off count, PostgREST grant count) and fails if
any of those guards regress.

## 0a. Phase 2 — done for you, three things to check

I applied migration `0003_orders_and_addresses` to the **live** project through
the Supabase connector on 2026-11-25 (drift-checked afterwards: 11 tables, RLS on
all of them, `alembic_version` = `0003_orders_and_addresses`). So the store can
already take orders — the four things only you can do:

- ☐ **Place one real test order yourself** once the API is deployed: add two
  items, check the ₹500 minimum message, check out with cash on delivery, then
  open *Admin → Orders* and walk it through *Shipped → Out for delivery →
  Delivered*. You should see the timeline fill in and the payment flip to paid.
  (Costs you nothing: it is your own shop and your own cash.)
- ☐ **Confirm the delivery promise.** Today it is `default_delivery_days = 1`
  from `store_settings`, and checkouts only accept the pincodes in
  `serviceable_pincodes` (`125104`, `125201`). Tell me if either should change —
  it is a one-row edit, no deploy.
- ☐ **Map pin ("use my location")**: the address form is manual entry today. A
  map needs a Google Maps or Mapbox key (free tier is fine) plus the browser
  geolocation permission — send a key and I will add it in the location phase.
- ☐ **Notifications are now in** (Phase 3): a bell in the header with a red dot,
  a `/notifications` page, and a red count on *Admin → Orders* that updates every
  minute. Nothing is needed from you to use it — but the **emails will be recorded
  as `skipped`** until you send me a Resend key (section 2 below), because there is
  deliberately no fake mail provider. That is visible, not silent: every skipped row
  carries the reason.

## 1. Supabase (database, auth, storage)

- ☐ 🔑 Create **two** projects (or one now, one at staging time):
  - `tripat-msgstore-staging` (region: Mumbai / ap-south-1)
  - `tripat-msgstore-prod`
- ☐ 🔑 Send me, per project: project URL, **anon** key, **service_role** key,
  pooled connection string (transaction mode, port 6543), direct connection
  string (port 5432) and the database password.
- ☐ In each project: Authentication → Providers → enable **Email** (password).
- ☐ 🕒 Enable **Google** provider (needs step 6 first), then send me the client ID
  and secret.
- ☐ Authentication → URL configuration → Site URL + redirect allowlist
  (`https://<your-domain>`, `https://<your-domain>/auth/callback`,
  `http://localhost:5173/auth/callback`).
- ☐ Storage → confirm bucket `catalog` exists after my migration runs
  (public read, writes only through the backend).
- ☐ Backups: check the plan. Free tier has daily backups only; **PITR** needs Pro.
  Tell me which you have so `docs/DEPLOY.md` matches reality.

## 2. Resend (email)

- ☐ 🔑 Create a Resend account, add and **verify the sending domain** (SPF, DKIM,
  DMARC records at your DNS provider). Gmail/Yahoo addresses cannot be used as
  the From domain.
- ☐ 🔑 Send me the API key and the verified From address, e.g.
  `Tripat Pansari <orders@yourdomain.in>`.
- ☐ Add DMARC (`v=DMARC1; p=quarantine; rua=mailto:tripatinsan029@gmail.com`).

## 2a. Phase 3 — done for you, two things to check

Migration `0004_notifications_and_email` is applied to the **live** project
(verified 2026-11-25: 13 tables, RLS on 13/13, `alembic_version` =
`0004_notifications_and_email`). Two things worth a minute:

- ☐ **Check the bell says the right thing.** Place a test order, then look at the
  header: you should have one unread notification as the customer *and* one as the
  shop (add your own email to `ADMIN_EMAILS` if you have not — that list decides
  who gets "New order"). Move the order to *Shipped* and the customer's bell should
  gain a second line.
- ☐ **Decide whether you want email at all.** If yes, section 2 (Resend) — one key
  and one verified From address and the queued confirmations start going out. If
  no, say so and I will leave the outbox switched off; the bell alone still covers
  "your order shipped".

## 2b. Phase 4 — done for you, one thing to try

Migration `0005_wallet_referrals_rewards` is applied to the **live** project
(verified 2026-11-25: 19 tables, RLS on 19/19, `alembic_version` =
`0005_wallet_referrals_rewards`). The customer app now has **Rewards** (wallet
statement, referral code, scratch cards, badge) and an order can be returned from
its own page; the owner gets a new **Returns** tab.

- ☐ **Try the two-tap promise.** Open a delivered order as the customer, ask to
  return one item, then go to *Admin → Returns*. Approve it: the customer's wallet
  must stay unchanged. Tap *Goods received · credit wallet*: the money appears,
  once. That second tap is the only thing that pays a customer back.

## 2c. Phase 5 — done for you, four things to try

Migration `0006_owner_tools` is applied to the **live** project (verified
2026-11-25: 22 tables, RLS on 22/22, 264/264 columns matching the code, digest
`999d3e5e…2458`, `alembic_version` = `0006_owner_tools`). The admin side now has
**Products**, **Categories**, **Brands**, **Offers**, **Inbox** and **Activity**
tabs, and the storefront has a real **Contact** page.

- ☐ **Add one item the way you actually will.** *Admin → Products*, type a name,
  pick the shelf, type the price in rupees, press *Add product*. Open the shop in
  another tab: it is there, no waiting. (This is A-07.)
- ☐ **Paste a sheet and break one line on purpose.** *Admin → Products → Bulk
  add*. Put a real category slug on one line and nonsense on another, press
  *Preview*. It must tell you the line number and refuse to save anything.
  Fix the bad line, preview again, then save. (A-08.)
- ☐ **Delete something that has been ordered.** Delete a product you have sold.
  It will say it was *hidden* rather than deleted — open the old order and the item
  is still named there. That is deliberate. (A-09.)
- ☐ **Change a number and watch it bite.** *Admin → Settings*, raise the minimum
  order, save, then try to check out a smaller cart as a customer. It is refused
  straight away, and *Activity* shows the old and new value next to your email.
  (A-15, S-12.)
- ☐ 🕒 **Photo upload needs one thing from you.** Create/confirm the public
  Storage bucket named `catalog` and send me the **service-role** key for the
  backend (never the frontend). Until then the upload button answers
  *"Image storage is not configured"* and you can still paste an image URL.

## 3. Domain

- ☐ 🔑 Buy the domain (suggest `tripatpansari.in` / `msgstore.in`).
- ☐ Point the apex at Vercel, `www` → redirect to apex, optionally
  `api.` at the backend host. I will give you the exact DNS records after you
  tell me the host (Render / Railway / Fly.io).

## 4. Hosting accounts

- ☐ 🔑 Vercel account → create project from this repo (root directory
  `apps/web`). Send me the project/org IDs and a deploy token for CI.
- ☐ 🔑 Backend host — pick one: **Render** (recommended: always-on Starter),
  Railway or Fly.io. Create the service from `infra/`, send me the deploy hook URL
  and the service URL.
- ✅ No cache service to buy. Rate limits are counted in your own database, so
  there is no Upstash/Redis signup and no key to send. (Earlier drafts of this
  list asked for one; that requirement is gone.)

## 5. Bot protection (only if we enable Turnstile)

- ☐ 🔑 Cloudflare Turnstile site + secret key. Leave `TURNSTILE_ENABLED=false`
  until you have them; signup/feedback still work but without the challenge.

## 6. Google OAuth (for "Continue with Google")

- ☐ 🔑 Google Cloud project → OAuth consent screen (External, publish it) →
  OAuth client (Web application) with authorised redirect
  `https://<project-ref>.supabase.co/auth/v1/callback`.
- ☐ Send me the client ID/secret so I can enable the provider in Supabase.

## 7. Content only you can supply

- ☐ 🔑 **Logo**: 110×110 PNG or SVG (transparent background preferred). Drop it at
  `apps/web/public/brand/logo.png`; I regenerate every icon from it.
- ☐ 🔑 **Google Maps short link** for the shop → `STORE_MAPS_URL`.
- ☐ 🔑 **Real product list and photographs**. Until they arrive the seed catalogue
  uses clearly-labelled sample rows; photographs must be yours (brand images need
  permission).
- ☐ 🔑 Confirm the phone number and address wording exactly as you want it shown.
- ☐ 🔑 Hindi copy review when we add the Hindi UI (final phase).

## 8. Legal and policy

- ☐ 🔑 **Review the privacy policy and terms** (`/policies/privacy`, `/policies/terms`)
  before you take a single real order. They describe what we actually collect:
  name, phone, email, delivery address.
- ☐ Decide the account-deletion contact and turnaround (default: in-app request,
  7 days).

## 9. Decisions I need from you (short answers)

- ☐ Do you want SMS OTP later? If yes, you will need an Indian SMS provider **plus
  DLT registration** of headers and templates — that is a 1–3 week process and
  cannot be bypassed.
- ☐ Free Supabase tier pauses after 7 days of inactivity. For a live shop you want
  the Pro plan. Confirm.
- ☐ Who besides you should have admin access? (Each person needs their own login;
  never share one.)
