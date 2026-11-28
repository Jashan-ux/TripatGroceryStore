import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AdminInventoryPage } from '@/admin/AdminInventoryPage';
import { renderWithProviders } from '@/test/render';

const productId = '11111111-1111-1111-1111-111111111111';
const variantId = '22222222-2222-2222-2222-222222222222';
const product = {
  id: productId,
  name: 'Loose Basmati Rice',
  slug: 'loose-basmati-rice',
  description: '',
  category_id: '33333333-3333-3333-3333-333333333333',
  category_name: 'Rice',
  category_slug: 'rice',
  brand_id: null,
  brand_name: '',
  unit_label: 'loose',
  mrp_paise: 12000,
  price_paise: 10000,
  stock: 0,
  low_stock_threshold: 5,
  images: [],
  tags: [],
  rating: 0,
  is_active: true,
  variants: [
    {
      id: variantId,
      label: '1 kg',
      mrp_paise: 12000,
      price_paise: 10000,
      stock: 3,
      sort_order: 0,
      is_active: true,
    },
  ],
  available_stock: 3,
  created_at: '2026-11-01T10:00:00Z',
  updated_at: '2026-11-01T10:00:00Z',
};

function mockFetch() {
  const calls: { url: string; method: string; body: unknown }[] = [];
  let stock = 3;
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? 'GET';
      const body = typeof init?.body === 'string' ? JSON.parse(init.body) : null;
      calls.push({ url, method, body });
      const json = (payload: unknown) =>
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      if (url.includes('/variants/') && method === 'PATCH') {
        stock = (body as { stock: number }).stock;
        return json({
          ...product,
          variants: [{ ...product.variants[0], stock }],
          available_stock: stock,
        });
      }
      if (url.includes('/api/v1/admin/catalogue/products')) {
        const current = {
          ...product,
          variants: [{ ...product.variants[0], stock }],
          available_stock: stock,
        };
        return json({ items: [current], total: 1, page: 1, page_size: 20, total_pages: 1 });
      }
      return json({ error: { code: 'not_found', message: 'no' } });
    }),
  );
  return calls;
}

describe('AdminInventoryPage', () => {
  beforeEach(() => vi.unstubAllGlobals());

  it('counts pack-level stock and saves an audited inventory adjustment', async () => {
    const calls = mockFetch();
    const user = userEvent.setup();
    renderWithProviders(<AdminInventoryPage />, { route: '/admin/inventory' });

    expect(await screen.findByText('Loose Basmati Rice')).toBeInTheDocument();
    expect(screen.getByText('3 available')).toBeInTheDocument();
    const count = screen.getByRole('spinbutton', { name: 'Loose Basmati Rice (1 kg) stock count' });
    await user.clear(count);
    await user.type(count, '12');
    await user.click(screen.getByRole('button', { name: 'Save count' }));

    await waitFor(() => {
      const patch = calls.find((call) => call.method === 'PATCH');
      expect(patch?.url).toContain(`/products/${productId}/variants/${variantId}/stock`);
      expect(patch?.body).toMatchObject({ stock: 12, note: 'Inventory count adjustment' });
    });
    expect(await screen.findByText('Loose Basmati Rice (1 kg) stock saved.')).toBeInTheDocument();
  });
});
