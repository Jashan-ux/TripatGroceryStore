# Deploy runbook

Environments: **local** → **staging** → **production**. Nothing here is done for
you; every step says exactly where to click and what to paste. Secret values go
into the host's secret store, never into git.

Names used below (change them consistently if you prefer different ones):

| Thing | Value |
|---|---|
| Production web | `https://tripatpansari.in` (apex) + `www` → redirect |
| Production API | `https://tripat-msgstore-api.onrender.com` (or `api.tripatpansari.in`) |
| Staging web | `https://staging.tripatpansari.in` (or the Vercel preview URL) |
| Staging API | `https://tripat-msgstore-api-staging.onrender.com` |
| Staging DB | separate Supabase project |
| Production DB | separate Supabase project |

---

## 0. Prerequisites (local machine)

```bash
node --version   # 22.x
npm --version    # 10.x
python --version # 3.12
docker --version # optional, only for compose
supabase --version
```

`npm ci` at the repo root installs both workspaces.

---

## 1. Supabase — two projects

1. <https://supabase.com/dashboard> → **New project**.
2. Name `tripat-msgstore-staging`, region **Mumbai (ap-south-1)**, strong DB
   password (save it in your password manager — it is not retrievable later).
3. Repeat for `tripat-msgstore-prod`.
4. For each project, collect (Project Settings):
   - **API URL** → `SUPABASE_URL`
   - **anon public** key → `SUPABASE_ANON_KEY`
   - **service_role** key → `SUPABASE_SERVICE_ROLE_KEY` *(backend only)*
   - **Connection pooling → Transaction mode**, port `6543`
     → `DATABASE_URL` = `postgresql+asyncpg://postgres.<ref>:<password>@aws-0-ap-south-1.pooler.supabase.com:6543/postgres`
   - **Direct connection**, port `5432`
     → `DATABASE_DIRECT_URL` = `postgresql+asyncpg://postgres:<password>@db.<ref>.supabase.co:5432/postgres`
5. **Auth → Providers**: enable Email. Leave "Confirm email" on for production.
6. **Auth → URL configuration**:
   - Site URL: `https://tripatpansari.in`
   - Redirect URLs: `https://tripatpansari.in/auth/callback`,
     `https://staging.tripatpansari.in/auth/callback`,
     `http://localhost:5173/auth/callback`,
     `https://*-<your-vercel-team>.vercel.app/auth/callback` (preview deploys)
7. **Storage**: create a bucket named `catalog`, **public read**, no public write.
   Uploads happen only through the backend with the service-role key. Set
   `SUPABASE_STORAGE_BUCKET=catalog` (the default) on the API host. Without
   `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` the upload endpoint answers
   `503 image_upload_unavailable` — the shop still works, images can be pasted as
   URLs. Uploaded photos are re-encoded to WebP before they are stored, so the
   bucket only ever holds images this backend produced.
8. **Backups**: note what your plan gives you. Free = daily, no PITR. Pro = PITR.
   Record it in §9 below.

### Apply the schema (Alembic owns it)

```bash
cd apps/api
python -m venv .venv && . .venv/bin/activate
pip install -e .
export DATABASE_DIRECT_URL='postgresql+asyncpg://postgres:<password>@db.<ref>.supabase.co:5432/postgres'
alembic upgrade head
```

Verify in the SQL editor (should return rows for `alembic_version` and the
hardening trigger):

```sql
select * from alembic_version;
select tgname from pg_trigger where tgname = 'trg_harden_public_table';
```

> **Never** use `supabase db push` or the dashboard table editor on these
> projects. The schema is Alembic's; the dashboard is for inspection only.

---

## 2. Resend (email)

1. <https://resend.com> → **Domains → Add domain** → `tripatpansari.in`.
2. Add the SPF, DKIM and DMARC records it shows you at your DNS provider.
   DMARC: `v=DMARC1; p=quarantine; rua=mailto:tripatinsan029@gmail.com`.
3. Wait for "Verified" (minutes to a few hours).
4. **API keys → Create** → copy → `RESEND_API_KEY`.
5. From address: `Tripat Pansari <orders@tripatpansari.in>` → `SUPPORT_EMAIL_FROM`.

---

## 3. Backend host (Render, recommended)

1. <https://dashboard.render.com> → **New → Blueprint** → connect this repo →
   it reads `infra/render.yaml`.
2. Set every `sync: false` env var (staging values in the staging service):

   | Key | Value |
   |---|---|
   | `ENVIRONMENT` | `production` |
   | `WEB_ORIGIN` | `https://tripatpansari.in` |
   | `DATABASE_URL` | pooled URL (§1) |
   | `DATABASE_DIRECT_URL` | direct URL (§1) |
   | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | §1 |
   | `REDIS_URL` | §4 |
   | `RESEND_API_KEY`, `SUPPORT_EMAIL_FROM` | §2 |
   | `STORE_MAPS_URL` | owner-supplied short link |
   | `ADMIN_EMAILS` | owner's login email(s), comma separated |
   | `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY`, `VAPID_SUBJECT` | §5 |

3. Deploy. The container runs `alembic upgrade head` is **not** in the start
   command on purpose — migrations run from CI before the deploy (see
   `.github/workflows/deploy-production.yml`), so a bad migration cannot take the
   service down mid-boot.
4. Confirm `https://<api-host>/healthz/ready` returns 200 and
   `https://<api-host>/docs` returns **404**.

**Fly.io alternative**: `cd apps/api && fly launch --no-deploy --copy-config`,
`fly secrets set ...`, `fly deploy`. **Railway**: new project from repo,
`infra/railway.json` supplies the Dockerfile path and healthcheck.

---

## 4. Redis (Upstash)

1. <https://console.upstash.com> → **Create database** → region closest to the API
   (Mumbai/Singapore), TLS enabled.
2. Copy the **TLS** connection string (`rediss://…`) → `REDIS_URL`.
3. Production boot fails without it on purpose: in-memory limits are per-instance.

---

## 5. Web Push keys (once)

```bash
npx web-push generate-vapid-keys
# Public Key:  B...
# Private Key: ...
```

`VAPID_PUBLIC_KEY` / `VAPID_PRIVATE_KEY` go to the backend secrets;
`VAPID_SUBJECT` is `mailto:tripatinsan029@gmail.com`.

---

## 6. Google OAuth

1. <https://console.cloud.google.com> → new project "Tripat MSG Store".
2. **APIs & Services → OAuth consent screen**: External, app name
   "Tripat Pansari · MSG Store", support email, developer email, scopes
   `email`, `profile`, `openid`. Publish.
3. **Credentials → Create → OAuth client ID → Web application**:
   - Authorised JavaScript origins: `https://tripatpansari.in`,
     `https://staging.tripatpansari.in`, `http://localhost:5173`
   - Authorised redirect URI: `https://<project-ref>.supabase.co/auth/v1/callback`
4. Paste client ID/secret into Supabase **Auth → Providers → Google**, enable it.
5. Add `GOOGLE_OAUTH_CLIENT_IDS` to the backend so it can verify the `aud` claim
   for Google-issued tokens.

---

## 7. Frontend on Vercel

1. <https://vercel.com/new> → import this repo.
2. **Root Directory**: `apps/web`. Framework preset: Vite.
   Build command and output directory come from `vercel.json`.
3. Because robots/`vercel.json` needs the backend origin, add an environment
   variable to the CI job (`vars.PRODUCTION_API_ORIGIN`) — the workflow renders
   `vercel.json` from `vercel.json.template` before deploying.
   When deploying by hand:
   ```bash
   cd apps/web
   API_ORIGIN=https://tripat-msgstore-api.onrender.com node scripts/render-host-config.mjs
   vercel --prod
   ```
4. **Settings → Domains**: add `tripatpansari.in` and `www.tripatpansari.in`
   (set `www` → 308 redirect to apex). Vercel issues the certificate
   automatically once DNS points at it.
5. Build-time env: leave `VITE_API_BASE_URL` **empty** (same-origin rewrites).
   `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` may also stay empty: the app
   reads them from `/api/v1/config` at runtime.

**Netlify alternative**: `netlify.toml` is generated the same way
(`API_ORIGIN=… node scripts/render-host-config.mjs`); Netlify cannot run FastAPI,
so the backend still lives on Render/Fly/Railway.

### DNS records (apex on Vercel)

| Type | Name | Value |
|---|---|---|
| A | `@` | `76.76.21.21` |
| CNAME | `www` | `cname.vercel-dns.com` |
| CNAME | `api` | `<your-backend-host>` (only if you use `api.` rather than the host domain) |

---

## 8. CI/CD wiring

GitHub → Settings → Secrets and variables → Actions:

| Kind | Name | Purpose |
|---|---|---|
| secret | `VERCEL_TOKEN` | `vercel` CLI deploys |
| secret | `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` | which project |
| secret | `RENDER_STAGING_DEPLOY_HOOK`, `RENDER_PRODUCTION_DEPLOY_HOOK` | host deploys |
| secret | `STAGING_DATABASE_DIRECT_URL`, `PRODUCTION_DATABASE_DIRECT_URL` | migrations |
| var | `STAGING_API_BASE_URL`, `STAGING_API_ORIGIN` | readiness + rewrites |
| var | `PRODUCTION_API_ORIGIN`, `PRODUCTION_WEB_URL` | production deploy + smoke |

Flow: every PR runs `ci.yml`. A push to `main` runs `deploy-staging.yml`
(migrate → deploy API → wait ready → deploy web). A tag `v*.*.*` runs
`deploy-production.yml` (migrate → API → web → smoke test). Approvals are enforced
by the GitHub Environments (`staging`, `production`).

---

## 9. Backups and restore drill

- Supabase takes daily backups on all plans; **PITR** only on Pro+.
- **Restore drill (do this once per quarter and write the date here):**
  1. Create a throwaway project `tripat-restore-drill`.
  2. Restore the latest backup (Supabase dashboard → Database → Backups →
     Restore, target = the throwaway project).
  3. Point a local API at the restored DB (`DATABASE_DIRECT_URL=…`) and run
     `alembic current` — it must print `0001_baseline (head)`.
  4. Run the smoke test in §10 against the throwaway project.
  5. Delete the throwaway project and record the result below.

| Date | Restored backup | Result | Notes |
|---|---|---|---|
| *(pending first drill — requires the owner's Supabase project)* | | | |

---

## 10. Post-deploy smoke test (5 minutes, every deploy)

```bash
API=https://tripat-msgstore-api.onrender.com
WEB=https://tripatpansari.in

curl -fsS $API/healthz/ready | jq '.status'          # "ok"
curl -fsS -o /dev/null -w '%{http_code}\n' $API/docs  # 404 in production
curl -fsS $WEB/manifest.webmanifest | jq '.short_name' # "MSG"
curl -fsS $WEB/api/v1/config | jq '.store_phone'       # same-origin rewrite works
```

Then, in a private browser window at 360 px width:

1. **Sign up** with a real email → you land on the storefront, still logged in
   after a hard refresh and after closing/reopening the browser (C‑05).
2. **Add a product**, place a **COD order** above ₹500 → confirmation shows
   `TP-0001xx` and "Deliver in 1 day(s) by <date>" (C‑09, C‑10).
3. Log in as the **merchant** → the order appears at the top of Orders with a red
   dot; open it, set **Shipped**, then **Delivered** (A‑02, A‑05, C‑11).
4. The customer sees the status change, the banner and gets an **email**
   (check the Resend dashboard → Emails → delivered).
5. `/admin` in a normal customer session redirects away and the API returns 403
   (A‑01).

Roll that back on any failure: Vercel → Deployments → previous deployment →
**Promote to Production**; Render → Events → previous deploy → **Redeploy**. This
is safe because every migration is additive until the next phase.

---

## 11. Rollback

| What | How | Caveat |
|---|---|---|
| Frontend | Vercel → Deployments → previous → Promote | instant, no data impact |
| Backend | Render → Events → previous deploy → Redeploy | keeps DB as is |
| Migration | `cd apps/api && alembic downgrade -1` against the **direct** URL | only safe if the deploy that needed it is rolled back first |
| Service worker | Deploys change `/sw.js`; the app shows "update available" | users on an old SW still get fresh HTML because `index.html` is `no-cache` |

---

## 12. Hardening checks after the first production deploy

- <https://securityheaders.com/?q=https://tripatpansari.in> → expect **A**
  (CSP, HSTS, nosniff, referrer policy, frame options are all in `vercel.json`).
- <https://www.ssllabs.com/ssltest/analyze.html?d=tripatpansari.in> → expect **A**.
- Supabase REST with the anon key must return nothing:
  ```bash
  curl -s "$SUPABASE_URL/rest/v1/profiles?select=*" -H "apikey: $SUPABASE_ANON_KEY" | jq
  # expect: {"code":"42501", ...} or an empty array
  ```
- Send yourself a complaint through the Contact page; confirm it arrives at
  `tripatinsan029@gmail.com` **and** in the admin feedback inbox.
