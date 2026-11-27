# Assumptions

Where the brief was silent, ambiguous or contradicted itself, this is what I did
and why. Each line states the safer option where security was involved.

## Environment and tooling

1. **Python 3.12 is the target, 3.11 is the floor.** `pyproject.toml` declares
   `>=3.11,<3.13`; the Docker image and CI both run **3.12**. This sandbox only
   has 3.11 and cannot download a 3.12 build, so local test runs here were on
   3.11. No 3.12-only syntax is used. Flagged because it is a real deviation.
2. **No Docker, no Postgres and no browser in this sandbox.** Postgres-backed
   tests are written and wired for CI (service container) and are skipped with a
   visible reason when `TEST_DATABASE_URL` is unset — never silently "passed".
   Playwright specs run in CI; where a screenshot was expected, I used a live
   preview instead and said so.
3. **Vercel and Netlify cannot interpolate env vars into their config files.**
   The backend origin therefore lives in `vercel.json.template` /
   `netlify.toml.template` and is rendered at deploy time by
   `apps/web/scripts/render-host-config.mjs`. The current rendered files point
   at the deployed Render backend `tripatgrocerystore.onrender.com`; CI deploy
   jobs still require the matching API origin in their environment variables.
4. **Node 22 + npm workspaces** for the monorepo. Frontend stack: Vite 7,
   Vitest 5, Tailwind 3.4, shadcn-style primitives on Radix, React 18.3 as
   required by the brief. Lockfiles are committed; Dependabot keeps them fresh.

## Product decisions

5. **Delivery days** are integers 0–7, default 1 (0 = same day). The date shown is
   always computed in `Asia/Kolkata` at render time and stored as a `date`.
6. **Minimum order** is compared against the **subtotal before** wallet and
   coupon, exactly as the brief says. Referral discount does not lower the gate.
7. **Wallet vs coupon stacking**: both may apply in one order; the referral
   discount is applied first (it is a price reduction on the first order), then
   the wallet covers up to the remaining total. Wallet can never take a total
   below ₹0, and a COD order with a fully wallet-covered total is still COD
   (payment_status `paid` at placement, nothing to collect).
8. **Scratch card coupon** is a single-use wallet-equivalent `coupon_discount` on
   the *next* order. It cannot be combined with the referral first-order discount
   (a first order uses the referral; the card waits). Cards expire after 30 days.
9. **Returns** credit `item_price × qty − proportional discount share`, rounded
   half-up per line, and the credit is a wallet ledger entry referencing the
   return id (unique index prevents a double credit).
10. **Loyalty tiers** are inclusive at the boundary (₹20,000 exactly → Gold) and
    are recalculated on delivery *and* on return credit, so the number in the
    badge always equals delivered spend net of returns.
11. **Guest cart** lives in `localStorage` under a versioned key, merges on login
    by summing quantities and capping at available stock; lines whose product was
    deleted or deactivated are dropped with a notice.

## Infrastructure decisions

12. **Backend host: Render, Starter plan, Singapore/Mumbai region, always-on.**
    Fly.io config included as an alternative (`infra/fly.toml`); Vercel Python
    functions are explicitly *not* used (cold starts, no background work).
13. **No cache service.** Rate limits are counted in Postgres
    (`rate_limit_counters`), so nothing extra has to be bought, and no deploy
    resets a budget. This replaced an earlier assumption that Upstash Redis was
    mandatory; requiring a service to *protect* the shop, and refusing to boot
    without it, was the wrong shape for one merchant with one API container.
14. **Sentry** is optional (`SENTRY_DSN` empty = disabled) and is configured with
    `send_default_pii=False`, no request bodies and no breadcrumbs.
15. **Email** is Resend only; every send goes through one service with HTML +
    text templates and HTML-escaped user text. No email is sent on a request path
    that could block the response — sends are queued in-process and failures are
    logged, not retried forever.
16. **Push**: VAPID keys are generated once by the owner (`npx web-push
    generate-vapid-keys`), stored as backend secrets. Subscriptions are pruned on
    404/410 from the push service.

## Security decisions

17. **Role comes only from `profiles.role`**, re-read per request; the JWT's
    `user_metadata` is never trusted. Admin bootstrap is `ADMIN_EMAILS` applied at
    seed time only — it cannot elevate a live request.
18. **Supabase anon key in the browser is fine; the REST API is dark.** Every
    public table gets `ENABLE ROW LEVEL SECURITY` with **no** policies for
    `anon`/`authenticated`, and grants are revoked — enforced automatically by an
    event trigger installed in the baseline migration so a future table cannot
    forget.
19. **Rate limiting** keys on user id when authenticated, else IP. Tests that
    assert limits trip use a real Redis in CI.
20. **CSP has no inline scripts** and no third-party scripts at all. The only
    external origins allowed are Supabase and OpenStreetMap tiles. This is why
    there is no analytics vendor in the app.
21. **`/docs`, `/redoc` and `/openapi.json` are off in production**; the schema is
    dumped at build time into `packages/api-client/openapi.json` and CI fails if
    it drifts from the code.

## Deliberate deferrals

22. Hindi UI, the delivery-person role, and SMS OTP are out of scope for this
    build (the role enum reserves `delivery`, and OTP sits behind
    `PHONE_OTP_ENABLED=false` with a provider interface).
23. Phase 0 ships the shell with honest empty states (no mock products). Catalogue
    data and product rails arrive in Phase 1; the placeholder pages state that
    plainly and offer tap-to-call instead of pretending to be broken.
