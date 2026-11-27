import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';

/**
 * P-01 installability. These assertions need the built app: `vite dev` neither
 * emits a service worker nor serves the generated manifest, so this file runs
 * against `vite preview` of a fresh production build (see playwright.config.ts).
 */
const PREVIEW_ORIGIN = `http://127.0.0.1:${process.env.E2E_PREVIEW_PORT ?? 4173}`;

test.describe('P-01 PWA installability', () => {
  test.use({ baseURL: PREVIEW_ORIGIN });
  test('manifest declares name, icons, start_url and scope', async ({ request }) => {
    const response = await request.get('/manifest.webmanifest');
    expect(response.ok()).toBeTruthy();
    const manifest = (await response.json()) as {
      name: string;
      short_name: string;
      start_url: string;
      scope: string;
      theme_color: string;
      icons: { sizes: string; purpose?: string; src: string }[];
    };
    expect(manifest.name).toBe('Tripat Pansari · MSG Store');
    expect(manifest.short_name).toBe('MSG');
    expect(manifest.start_url).toBe('/');
    expect(manifest.scope).toBe('/');
    expect(manifest.theme_color.toUpperCase()).toBe('#B91C1C');
    const sizes = manifest.icons.map((icon) => icon.sizes);
    expect(sizes).toContain('192x192');
    expect(sizes).toContain('512x512');
    expect(manifest.icons.some((icon) => icon.purpose === 'maskable')).toBe(true);
  });

  test('a previously installed app shell serves client routes while offline', async ({
    page,
    context,
  }) => {
    await page.goto('/');
    await page.evaluate(async () => {
      await navigator.serviceWorker.ready;
    });
    await expect
      .poll(() => page.evaluate(() => navigator.serviceWorker.controller !== null))
      .toBe(true);

    await context.setOffline(true);
    try {
      await page.goto('/contact');
      await expect(page.getByRole('heading', { name: /contact/i })).toBeVisible();
    } finally {
      await context.setOffline(false);
    }
  });

  test('public contact route has no WCAG A/AA accessibility violations', async ({ page }) => {
    await page.goto('/contact');
    await expect(page.getByRole('heading', { name: /contact/i })).toBeVisible();

    const audit = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
      .analyze();
    expect(
      audit.violations.map(({ id, impact, help, nodes }) => ({
        id,
        impact,
        help,
        targets: nodes.flatMap((node) => node.target),
      })),
    ).toEqual([]);
  });

  test('service worker is served with selective offline caching and push handling', async ({
    request,
  }) => {
    const sw = await request.get('/sw.js');
    expect(sw.ok()).toBeTruthy();
    const body = await sw.text();
    expect(body).toContain('skipWaiting');
    expect(body).toContain('public-catalogue-v1');
    expect(body).toContain('notificationclick');
    // The catalogue cache is selective; the /api/ catch-all is network-only,
    // while installable offline app-shell navigation remains available.
    expect(body).toContain('/api/');
  });
});
