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
| Lighthouse PWA installability | Chrome DevTools → Lighthouse, throttled 4G, mobile |
| securityheaders.com grade A | production URL |
| Restore drill | `docs/DEPLOY.md` §9 |

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
