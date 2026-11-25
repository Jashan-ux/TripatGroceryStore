import { defineConfig, devices } from '@playwright/test';
/**
 * E2E runs against the real API (uvicorn) with the Vite dev server proxying
 * /api/*, so the browser sees one origin exactly like production. Mail and push
 * sinks are file-based under e2e/.sinks and read by the specs.
 *
 * Mobile is the primary target: 360×800, the smallest phone we support.
 */
const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 5173);
const API_PORT = Number(process.env.E2E_API_PORT ?? 8000);
export default defineConfig({
    testDir: './e2e',
    fullyParallel: true,
    forbidOnly: !!process.env.CI,
    retries: process.env.CI ? 2 : 0,
    workers: process.env.CI ? 2 : undefined,
    reporter: process.env.CI
        ? [['github'], ['html', { open: 'never' }], ['junit', { outputFile: 'test-results/junit.xml' }]]
        : [['list'], ['html', { open: 'never' }]],
    timeout: 45_000,
    expect: { timeout: 10_000 },
    use: {
        baseURL: `http://127.0.0.1:${WEB_PORT}`,
        trace: 'on-first-retry',
        screenshot: 'only-on-failure',
        video: 'retain-on-failure',
        locale: 'en-IN',
        timezoneId: 'Asia/Kolkata',
        // Deterministic clock for "deliver by" copy (C-10) once orders exist.
        ...(process.env.E2E_FAKE_CLOCK ? { clock: { install: true } } : {}),
    },
    projects: [
        {
            name: 'mobile-360',
            use: { ...devices['Pixel 5'], viewport: { width: 360, height: 800 }, isMobile: true },
        },
        {
            name: 'desktop-1280',
            use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 800 } },
        },
    ],
    webServer: [
        {
            command: 'cd ../api && .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port ' +
                `${API_PORT}`,
            url: `http://127.0.0.1:${API_PORT}/healthz`,
            reuseExistingServer: !process.env.CI,
            timeout: 60_000,
            env: { ENVIRONMENT: 'test', RATE_LIMIT_ENABLED: 'false' },
        },
        {
            command: `npm run dev -- --port ${WEB_PORT}`,
            url: `http://127.0.0.1:${WEB_PORT}`,
            reuseExistingServer: !process.env.CI,
            timeout: 120_000,
            env: { VITE_PROXY_API_ORIGIN: `http://127.0.0.1:${API_PORT}` },
        },
    ],
});
