import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AdminProductsPage } from '@/admin/AdminProductsPage';
import { renderWithProviders } from '@/test/render';

const configResponse = {
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

const ghee = {
  id: '11111111-1111-1111-1111-111111111111',
  name: 'Desi Ghee 1 L',
  slug: 'desi-ghee-1-l',
  description: '',
  category_id: '99999999-9999-9999-9999-999999999999',
  category_name: 'Ghee & Oils',
  category_slug: 'ghee-oils',
  brand_id: null,
  brand_name: 'Amul',
  unit_label: '1 L',
  mrp_paise: 66000,
  price_paise: 64000,
  stock: 4,
  low_stock_threshold: 5,
  images: [],
  tags: [],
  rating: 4.5,
  is_active: true,
  variants: [],
  available_stock: 4,
  created_at: '2026-11-01T10:00:00Z',
  updated_at: '2026-11-01T10:00:00Z',
};

const categories = {
  categories: [
    {
      id: '99999999-9999-9999-9999-999999999999',
      name: 'Ghee & Oils',
      slug: 'ghee-oils',
      parent_id: null,
      parent_name: '',
      emoji: '🫗',
      image_url: null,
      description: null,
      sort_order: 1,
      is_active: true,
      product_count: 3,
      child_count: 0,
      updated_at: '2026-11-01T10:00:00Z',
    },
  ],
};

interface Call {
  url: string;
  method: string;
  body: unknown;
}

function mockFetch() {
  const calls: Call[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? 'GET';
      calls.push({
        url,
        method,
        body: typeof init?.body === 'string' ? JSON.parse(init.body) : null,
      });
      const json = (payload: unknown, status = 200) =>
        new Response(JSON.stringify(payload), {
          status,
          headers: { 'Content-Type': 'application/json' },
        });

      if (url.includes('/api/v1/config')) return json(configResponse);
      if (url.includes('/api/v1/admin/catalogue/categories')) return json(categories);
      if (url.includes('/api/v1/admin/catalogue/brands')) return json({ brands: [] });
      if (url.includes('/api/v1/admin/catalogue/products/bulk')) {
        const body = JSON.parse(String(init?.body)) as { dry_run: boolean };
        return json({
          committed: !body.dry_run,
          total: 2,
          valid: 1,
          invalid: 1,
          created: body.dry_run ? 0 : 0,
          message: body.dry_run ? 'Nothing was written. 1 row needs fixing.' : 'Nothing saved.',
          rows: [
            {
              line: 2,
              status: 'ok',
              name: 'Toor Dal',
              slug: '',
              category: '',
              errors: [],
              product_id: null,
            },
            {
              line: 3,
              status: 'error',
              name: 'Mystery Item',
              slug: '',
              category: '',
              errors: ['Unknown category "no-such-shelf"'],
              product_id: null,
            },
          ],
        });
      }
      if (url.endsWith('/api/v1/admin/catalogue/products') && method === 'POST') {
        const body = JSON.parse(String(init?.body)) as { name: string };
        return json({ ...ghee, id: '22222222-2222-2222-2222-222222222222', name: body.name }, 201);
      }
      if (url.includes('/api/v1/admin/catalogue/products/') && method === 'DELETE') {
        return json({
          id: ghee.id,
          outcome: 'deactivated',
          message:
            'Desi Ghee 1 L is in 2 past order line(s), so it was hidden from the store instead of deleted. Its history stays intact.',
        });
      }
      if (url.includes('/api/v1/admin/catalogue/products')) {
        return json({ items: [ghee], total: 1, page: 1, page_size: 20, total_pages: 1 });
      }
      return json({ error: { code: 'not_found', message: 'no' } }, 404);
    }),
  );
  return calls;
}

describe('AdminProductsPage', () => {
  beforeEach(() => vi.unstubAllGlobals());

  it('lists products with price, stock and a low-stock warning', async () => {
    mockFetch();
    renderWithProviders(<AdminProductsPage />, { route: '/admin/products' });

    expect(await screen.findByText('Desi Ghee 1 L')).toBeInTheDocument();
    expect(screen.getByText('₹640')).toBeInTheDocument();
    // 4 ≤ threshold 5, so the stock number is called out.
    const stock = screen.getByText('4', { selector: 'td' });
    expect(stock.className).toContain('text-warning');
  });

  it('adds one product from the inline row and converts rupees to paise', async () => {
    const calls = mockFetch();
    const user = userEvent.setup();
    renderWithProviders(<AdminProductsPage />, { route: '/admin/products' });

    const form = await screen.findByRole('region', { name: /add one product/i });
    await user.type(within(form).getByLabelText('Name'), 'Fresh Paneer');
    await user.selectOptions(within(form).getByLabelText('Shelf'), ghee.category_id);
    await user.type(within(form).getByLabelText('Price (₹)'), '145.50');
    await user.type(within(form).getByLabelText('Stock'), '12');
    await user.click(within(form).getByRole('button', { name: /add product/i }));

    await waitFor(() => {
      const post = calls.find(
        (call) => call.url.endsWith('/api/v1/admin/catalogue/products') && call.method === 'POST',
      );
      expect(post?.body).toMatchObject({
        name: 'Fresh Paneer',
        category_id: ghee.category_id,
        price_paise: 14550,
        mrp_paise: 14550,
        stock: 12,
      });
    });
    expect(await screen.findByText(/is on the storefront now/i)).toBeInTheDocument();
  });

  it('previews a bulk sheet without writing, and shows which line is wrong', async () => {
    const calls = mockFetch();
    const user = userEvent.setup();
    renderWithProviders(<AdminProductsPage />, { route: '/admin/products' });

    await user.click(await screen.findByRole('button', { name: /bulk add/i }));
    const sheet = await screen.findByRole('textbox', { name: /paste your rows/i });
    await user.clear(sheet);
    await user.type(sheet, 'name,category,price{{enter}}Toor Dal,ghee-oils,145.50');
    await user.click(screen.getByRole('button', { name: /^preview$/i }));

    await waitFor(() => {
      const post = calls.find((call) => call.url.includes('/products/bulk'));
      expect(post?.body).toMatchObject({ dry_run: true });
    });
    expect(await screen.findByText(/1 row needs fixing/i)).toBeInTheDocument();
    expect(screen.getByText(/unknown category "no-such-shelf"/i)).toBeInTheDocument();
    // A sheet with an error cannot be saved from this dialog.
    expect(screen.getByRole('button', { name: /^save/i })).toBeDisabled();
  });

  it('says that a product in an order was hidden, not deleted', async () => {
    mockFetch();
    const user = userEvent.setup();
    renderWithProviders(<AdminProductsPage />, { route: '/admin/products' });

    await user.click(await screen.findByRole('button', { name: /delete desi ghee 1 l/i }));

    expect(
      await screen.findByText(/hidden from the store instead of deleted/i),
    ).toBeInTheDocument();
  });
});
