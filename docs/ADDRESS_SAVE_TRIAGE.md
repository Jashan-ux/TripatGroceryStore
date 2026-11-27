# Address save incident — 2026-11-25

## Finding

The address API contract is consistent end to end: the checkout sends the full
`AddressIn` shape to `POST /api/v1/addresses` (or `PUT /api/v1/addresses/{id}`
for edits); `CurrentUserDep` scopes the write to `user.profile`; the service
normalizes and commits the row, then returns `AddressOut` (201 for create, 200
for update). The repository flushes the ORM row, and the service commits before
returning it.

The confirmed front-end defect was a dependency collision. `apps/web/package.json`
listed `@hookform/resolvers` twice: runtime `7.0.9` and development `3.9.1`. The
lockfile selected the old `3.9.1` package. That resolver version does not handle
Zod 4's error shape; invalid address forms raised an unhandled `ZodError` rather
than rendering field-level validation feedback. The form's prior submit handler
also had no invalid-submit summary. For successful API writes, the saved
`AddressOut` was not inserted into the address query cache before the refetch,
so a failed follow-up GET could leave the form looking unchanged.

## Changes

- Removed the duplicate development dependency and regenerated `package-lock.json`
  so `npm ci` uses the runtime resolver version compatible with Zod 4.
- Added an accessible validation summary, API field-error mapping, pending state,
  and clear server-error feedback on the address form.
- Changed the checkout submit flow to await `mutateAsync`, catch all failures,
  and display a useful message rather than silently leaving the form unchanged.
- Insert the committed address into the React Query cache immediately, then
  invalidate/refetch in the background. A refetch failure no longer hides a
  successful save.
- Surface initial saved-address loading errors with a retry action.
- Added web regression tests for invalid input, backend failure/retry state, and
  successful creation when the post-save address refresh fails.
- Extended the API address CRUD integration test to exercise update + normalized
  phone response.

## Verification

- `npm run lint --workspace @tripat/web` — passed.
- `npm run typecheck --workspace @tripat/web` — passed.
- `npm test --workspace @tripat/web` — **19 files, 94 tests passed**.
- `uv run --project . ruff check app tests` — passed.
- `uv run --project . ruff format --check app tests` — passed.
- `uv run --project . mypy app` — passed.
- `uv run --project . pytest -q` from `apps/api` — passed; database-marked
  integration tests skip locally without `TEST_DATABASE_URL`.
- GitHub Actions [run 46011960767](https://github.com/Jashan-ux/TripatGroceryStore/actions/runs/46011960767)
  — all six jobs passed on `daae892`, including API PostgreSQL migration/
  integration tests, web lint/typecheck/unit/build, E2E, Lighthouse, and Security.
  This includes the added address-update assertion.
- npm audit currently reports **4 moderate** advisories in the PWA/Workbox
  dependency chain; `npm audit --omit=dev --audit-level=high` reports no
  production vulnerabilities. No force upgrade was applied because npm's
  proposed fix downgrades `vite-plugin-pwa` across a breaking version boundary.

## Deployment/acceptance state

- Vercel connector reports production READY/PROMOTED on `tripatmsg.in` at
  commit `81e814b`; the deployment predates this fix. It also reports the current
  branch preview at commit `daae892` READY/STAGED at
  [the Vercel preview](https://tripat-grocery-store-1he3tz2ly-jashan-uxs-projects.vercel.app)
  (deployment `dpl_9NjZR7wBZ9PMwiPK9Vd4tHEaKSwv`). The preview is not the
  production domain. This branch is not the Vercel production branch, so the fix
  needs promotion/merge through the normal release path before it can be verified
  on the live domain.
- Render status could not be queried with the available connected tools. No
  credentials, secrets, or connection strings were accessed. Deploy the current
  API branch (which contains `47f5618`) to the existing Render service if that
  transaction-pooler fix is not already running; this address UI fix adds no
  database migration. Commit `8164f1f` was offer-link hardening and is not
  required for address persistence specifically.
- Supabase health check for the active project reports database, pooler, Auth,
  and REST healthy. This establishes service health, not that a real user's
  address mutation succeeded.
- Live authenticated address creation/update, direct-origin CORS, the Render
  `/healthz` probes, deployed-origin Lighthouse/full-site axe, and production
  push delivery remain manual/deployment checks. Do not mark them passed until
  run against the deployed service.
