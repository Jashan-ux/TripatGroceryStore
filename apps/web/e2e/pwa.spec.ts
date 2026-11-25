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

  test('service worker is served and never caches the API', async ({ request }) => {
    const sw = await request.get('/sw.js');
    expect(sw.ok()).toBeTruthy();
    const body = await sw.text();
    expect(body).toContain('skipWaiting');
    expect(body).toMatch(/NetworkOnly/);
  });
});
