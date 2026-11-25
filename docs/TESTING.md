# Testing

## Layers

| Layer | Tool | Runs where | Command |
|---|---|---|---|
| Backend unit + API behaviour | pytest + FastAPI `TestClient` | local, CI | `cd apps/api && pytest` |
| Backend integration (real Postgres/Redis) | pytest, markers `db` / `redis` | CI service containers | `TEST_DATABASE_URL=… pytest -m db` |
| Frontend unit + component | Vitest + React Testing Library | local, CI | `cd apps/web && npm run test` |
| End-to-end | Playwright, 360×800 and 1280×800 | CI (browsers are not downloadable in the build sandbox) | `cd apps/web && npm run test:e2e` |
| Bundle budget | custom script | local, CI | `node scripts/check-bundle-size.mjs` |
| Secrets | gitleaks (pre-commit + CI) | local, CI | `gitleaks detect --config .gitleaks.toml` |
| Supply chain | `pip-audit`, `npm audit --audit-level=high` | CI | see `ci.yml` |

### Running the database tests on your own machine

`pgserver` gives you a real, throwaway PostgreSQL without Docker. That is how the
Phase 5 migration (and its `0006` round-trip) and the 170 database-marked tests
were checked before CI:

```bash
cd apps/api && pip install pgserver

# 1. start a server in /tmp/pgdata and create the test database once
python -c "import pathlib,pgserver; pathlib.Path('/tmp/pgdata').mkdir(exist_ok=True); \
pgserver.get_server('/tmp/pgdata', cleanup_mode=None).psql('CREATE DATABASE tripat_test OWNER postgres;')"

# 2. the bundled server ships without contrib; the migrations need pg_trgm and
#    unaccent, so build them from the matching Postgres source (REL_16_2 here)
PG_CONFIG=$(python -c "import os,pgserver;print(os.path.join(os.path.dirname(pgserver.__file__),'pginstall/bin/pg_config'))")
curl -sL https://codeload.github.com/postgres/postgres/tar.gz/refs/tags/REL_16_2 | tar xz
for ext in pg_trgm unaccent; do
  (cd "postgres-REL_16_2/contrib/$ext" && make USE_PGXS=1 PG_CONFIG="$PG_CONFIG" && \
   make USE_PGXS=1 PG_CONFIG="$PG_CONFIG" install)
done

# 3. migrate both ways, then run everything
export DATABASE_URL="postgresql+asyncpg://postgres@/tripat_test?host=/tmp/pgdata"
export TEST_DATABASE_URL="$DATABASE_URL"
alembic upgrade head && alembic downgrade base && alembic upgrade head
pytest            # 396 passed, 1 skipped
```

One test skips there on purpose: the `anon`-role RLS probe needs Supabase's roles,
so it only runs against a Supabase database.

## Honest skipping

Tests that need infrastructure are **skipped with a reason**, never silently
passed:

```python
@pytest.fixture(scope="session")
def database_url() -> str:
    url = os.environ.get("TEST_DATABASE_URL", "")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set — database tests run in CI only")
    return url
```

`docs/ACCEPTANCE_REPORT.md` lists each scenario as **pass / fail / not run**, and a
scenario is only ever `pass` with a link to a green CI run or a recorded command
in this workspace.

## Test data

`apps/api/app/scripts/seed.py` (Phase 1) creates:

- `owner@<admin domain>` — admin (from `ADMIN_EMAILS`)
- `customer.staging@…` — a customer with a phone, address and delivered history
- `friend.staging@…` — a referred friend used for C‑13

It **refuses to run** when `ENVIRONMENT=production` and prints why.

## Fakes and sinks

- **Email**: `EmailService` writes HTML/text into `apps/api/.test-sinks/mail/*.json`
  when `ENVIRONMENT=test`; specs assert exact recipients and bodies.
- **Push**: same idea, `.test-sinks/push/*.json`, so push payloads are assertable
  without a device.
- **Clock**: Playwright installs a fake clock (`E2E_FAKE_CLOCK=1`) so
  "Deliver in 1 day(s) by <date>" is deterministic; the backend takes `now` from a
  single injectable clock in `app/core/clock.py`.
- **Geolocation and Nominatim**: mocked via route interception; no live calls in
  tests.
- **Payments**: none exist by design (COD only).

## Manual checklist (cannot be automated)

| Item | How to check |
|---|---|
| Real Google sign-in | staging, real Google account, confirm role is `customer` and email verified |
| Real iOS install (16.4+) | Safari → Share → Add to Home Screen → open standalone → push permission prompt appears |
| Real Web Push on Android | install, subscribe, place an order from another device, notification arrives |
| Real email delivery | Resend dashboard shows `delivered`, check spam folder once |
| Real photo upload | Admin → Products → edit → choose a phone photo; the returned URL must open from a different device (needs `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` and the public `catalog` bucket) |
| Lighthouse PWA installability | Chrome DevTools → Lighthouse, throttled 4G, mobile |
| securityheaders.com grade A | production URL |
| Restore drill | `docs/DEPLOY.md` §9 |

## What Phase 5 added, and where it lives

| File | Tests | What it proves |
|---|---|---|
| `tests/test_admin_catalogue.py` | 18 | inline add reaches the storefront, slugs stay unique, edit is audited, variants are replaced wholesale, delete vs deactivate, category reassign and nesting, brand guards, listing filters/pages |
| `tests/test_bulk_import.py` | 10 | all-or-nothing, per-row line numbers, exact rupee→paise, dry run writes nothing, BOM tolerance, header/empty/row-cap refusals, SSRF-filtered image URLs |
| `tests/test_uploads.py` | 28 | type allowlist, SVG/polyglot/GIF refusal, size and dimension caps, EXIF stripped, unique dated keys, `https`-only remote links, storage-not-configured |
| `tests/test_admin_offers_settings_feedback.py` | 19 | tier audience fan-out, public banner, offer href restriction, settings apply to the next checkout, set-level validation, feedback inbox + bell + email, audit trail order and privacy |

The web side adds `ContactPage.test.tsx`, `OfferBanner.test.tsx`,
`AdminProductsPage.test.tsx`, `AdminSettingsPage.test.tsx` and
`AdminOffersFeedback.test.tsx` — 19 tests that hold the screens to the promises
the API makes (rupees in / paise out, preview-before-commit, "hidden, not
deleted", dismissal that survives a reload).

## Writing a new test

Name it after the acceptance ID it proves:

```python
async def test_c_08_cart_below_minimum_blocked(client, customer_token):
    ...
```

or in Playwright:

```ts
test('C-08 cart under ₹500 is blocked with the exact shortfall', async ({ page }) => { … });
```
