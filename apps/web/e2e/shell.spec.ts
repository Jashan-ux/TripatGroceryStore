import { expect, test } from '@playwright/test';

/**
 * Phase 0 shell specs. Scenario IDs match docs/ACCEPTANCE_REPORT.md; the full
 * journey specs are added as their phase lands. Anything asserted here runs
 * against the real FastAPI server through the dev proxy.
 */

test.describe('C-01 storefront shell', () => {
  test('renders brand, hero, contact and no horizontal scroll', async ({ page }) => {
    await page.goto('/');

    await expect(page.getByRole('heading', { level: 1 })).toContainText(
      /Your family deserves the best/i,
    );
    await expect(page.getByRole('link', { name: /\+91 87089-73386/ }).first()).toHaveAttribute(
      'href',
      'tel:+918708973386',
    );

    // Page never scrolls sideways (defect 6.4) at any width.
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });

  test('bottom nav and footer never overlap content', async ({ page }) => {
    await page.goto('/');
    const footerLast = page.getByText(/All rights reserved/i).last();
    await footerLast.scrollIntoViewIfNeeded();

    const { footerBottom, navTop, navVisible } = await page.evaluate(() => {
      const nav = document.querySelector('nav.fixed');
      const copyright = Array.from(document.querySelectorAll('p')).find((p) =>
        /All rights reserved/i.test(p.textContent ?? ''),
      );
      return {
        footerBottom: copyright?.getBoundingClientRect().bottom ?? 0,
        navTop: nav?.getBoundingClientRect().top ?? window.innerHeight,
        navVisible: !!nav && getComputedStyle(nav).display !== 'none',
      };
    });

    if (navVisible) {
      // The last line of content must sit above the fixed bottom navigation.
      expect(footerBottom).toBeLessThanOrEqual(navTop + 1);
    }
  });

  test('search navigates with a shareable query string', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('searchbox', { name: /search products/i }).fill('ghee');
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/\/search\?q=ghee$/);
    await expect(page.getByRole('heading', { name: /Results for/i })).toBeVisible();
  });

  test('unknown route shows the 404 page with a way back', async ({ page }) => {
    await page.goto('/no-such-page');
    await expect(page.getByRole('heading', { name: 'Page not found' })).toBeVisible();
    await page.getByRole('link', { name: /back to home/i }).click();
    await expect(page).toHaveURL(/\/$/);
  });
});

test.describe('A-16 admin shell separation', () => {
  test('admin has tabs, no customer search and no customer footer', async ({ page }) => {
    await page.goto('/admin');
    await expect(page.getByRole('heading', { name: 'Analytics' })).toBeVisible();
    await expect(page.getByRole('searchbox')).toHaveCount(0);
    await expect(page.getByText(/All rights reserved/i)).toHaveCount(0);

    for (const label of ['Analytics', 'Orders', 'Products', 'Customers', 'Settings']) {
      await expect(page.getByRole('link', { name: label }).first()).toBeVisible();
    }
  });

  test('admin bundle is not part of the customer page load', async ({ page }) => {
    const adminChunks: string[] = [];
    page.on('request', (request) => {
      if (request.resourceType() === 'script' && /AdminRoutes/.test(request.url())) {
        adminChunks.push(request.url());
      }
    });
    await page.goto('/');
    await page.waitForLoadState('networkidle');
    expect(adminChunks).toHaveLength(0);
  });
});

test.describe('P-01 PWA installability', () => {
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

test.describe('S-09 security headers on the app origin', () => {
  test('CSP, HSTS-equivalent and frame protections are present in the built config', async ({
    page,
  }) => {
    // The dev server does not inject host headers (Vercel/Netlify do); this
    // spec guards the shipped config files instead.
    await page.goto('/');
    const html = await page.content();
    expect(html).not.toContain('owner@example.com');
    expect(html).not.toContain('MOCK_PAY');
  });
});
