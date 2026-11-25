# Screenshots

There is **no browser in the build sandbox** (no Chromium, and its system
libraries are unavailable), so phase screenshots are produced by CI, not by hand.

## Where they come from

`npx playwright test` in the `E2E · Playwright (360×800, 1280×800)` job attaches:

- `playwright-report` — HTML report with a screenshot per step (`trace` on first
  retry, `screenshot: only-on-failure`, `video: retain-on-failure`)
- `playwright-test-results` — raw PNGs, traces and videos

Open the latest green run → **Artifacts** → `playwright-report` → `index.html`.

## Capturing a deliberate set for a phase review

```bash
cd apps/web
npx playwright install --with-deps chromium
npx playwright test --project=mobile-360 --project=desktop-1280 --update-snapshots
```

To always keep full-page PNGs (not just failures), add to `playwright.config.ts`:

```ts
use: { screenshot: { mode: 'on', fullPage: true } }
```

## Live preview instead of a static image

While a phase is under review the dev server is running in the workspace:

- storefront: `http://localhost:5173/`
- admin shell: `http://localhost:5173/admin`
- API: `http://localhost:8000/healthz`, docs at `http://localhost:8000/docs`
  (local only — disabled in production)

The Arena preview panel proxies port 5173, so the rendered app can be inspected
at 360 px by resizing the panel.
