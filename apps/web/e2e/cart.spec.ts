import { expect, test, type Page } from '@playwright/test';

/**
 * Guest cart journey (K-01).
 *
 * The E2E job has no database, so the catalogue and quote endpoints are stubbed
 * at the network layer: what is under test here is the *client* — adding from a
 * card, the badge, persistence across reloads, and the fact that the cart page
 * renders the server's quote (₹30) rather than the price stored on the device
 * (₹25).
 */

const PRODUCT_ID = '11111111-1111-1111-1111-111111111111';

const config = {
  environment: 'test',
  store_name: 'Tripat Pansari MSG Store',
  store_phone: '+91 87089-73386',
  store_address: 'near Sabji Mandi, Mandi Dabwali, 125104',
  store_maps_url: '',
  feedback_email: 'store@example.com',
  phone_otp_enabled: false,
  turnstile_enabled: false,
  supabase_url: '',
  supabase_anon_key: '',
  vapid_public_key: '',
};

const card = {
  id: PRODUCT_ID,
  slug: 'palak',
  name: 'Palak',
  unit_label: '250 g',
  price_paise: 2500,
  mrp_paise: 3000,
  discount_percent: 17,
  image_url: null,
  in_stock: true,
  stock: 12,
  rating: 4.5,
  has_variants: false,
  brand_name: null,
  category_slug: 'vegetables',
};

const quote = {
  lines: [
    {
      product_id: PRODUCT_ID,
      variant_id: null,
      slug: 'palak',
      name: 'Palak',
      unit_label: '250 g',
      variant_label: '',
      image_url: '',
      quantity: 1,
      unit_price_paise: 3000,
      mrp_paise: 3000,
      line_total_paise: 3000,
      available_stock: 12,
      in_stock: true,
      issue: null,
    },
  ],
  subtotal_paise: 3000,
  delivery_fee_paise: 0,
  discount_paise: 0,
  total_paise: 3000,
  item_count: 1,
  minimum_order_paise: 50000,
  shortfall_paise: 47000,
  deliver_by: '2026-11-26',
  delivery_days: 1,
  pincode: null,
  pincode_serviceable: null,
  blocking_issues: [
    {
      code: 'minimum_order',
      message: 'Add ₹470 more to reach the ₹500 minimum order.',
      details: {},
    },
  ],
  can_checkout: false,
};

async function stubApi(page: Page) {
  // Regexes, not globs: the query string must match the list endpoint only.
  await page.route(/\/api\/v1\/config$/, (route) => route.fulfill({ json: config }));
  await page.route(/\/api\/v1\/home$/, (route) =>
    route.fulfill({ json: { categories: [], rails: [] } }),
  );
  await page.route(/\/api\/v1\/categories/, (route) => route.fulfill({ json: [] }));
  await page.route(/\/api\/v1\/brands/, (route) => route.fulfill({ json: [] }));
  await page.route(/\/api\/v1\/products\?/, (route) =>
    route.fulfill({ json: { items: [card], page: 1, page_size: 24, total: 1, total_pages: 1 } }),
  );
  await page.route(/\/api\/v1\/checkout\/quote$/, (route) => route.fulfill({ json: quote }));
}

test.describe('K-01 guest cart', () => {
  test('add from a product card, keep it across a reload and price it from the server', async ({
    page,
  }) => {
    await stubApi(page);
    await page.goto('/search?q=palak');

    // The card's own ADD button adds without leaving the results page.
    await page
      .getByRole('button', { name: /add palak to cart/i })
      .first()
      .click();
    await expect(page.getByRole('button', { name: 'Add one more Palak' })).toBeVisible();
    await expect(page).toHaveURL(/\/search\?q=palak/);

    // Guest cart survives a fresh document load (it lives in localStorage).
    await page.goto('/cart');
    await expect(page.getByRole('heading', { name: 'Your cart' })).toBeVisible();
    await expect(page.getByText('Palak').first()).toBeVisible();

    // The bill comes from the API quote (₹30), not from the stored ₹25.
    await expect(page.getByText('₹30').first()).toBeVisible();
    await expect(page.getByText(/Add ₹470 more/i)).toBeVisible();
    await expect(page.getByRole('link', { name: 'Proceed to checkout' })).toHaveAttribute(
      'aria-disabled',
      'true',
    );
  });

  test('the cart page is usable empty, with a way back to the shop', async ({ page }) => {
    await stubApi(page);
    await page.goto('/cart');

    await expect(page.getByText('Your cart is empty')).toBeVisible();
    await page.getByRole('link', { name: 'Start shopping' }).click();
    await expect(page).toHaveURL(/\/categories$/);
  });
});
