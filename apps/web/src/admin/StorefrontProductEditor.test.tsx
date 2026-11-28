import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { StorefrontProductEditor } from '@/admin/StorefrontProductEditor';
import { renderWithProviders } from '@/test/render';

const categoryId = '99999999-9999-9999-9999-999999999999';
const createdProduct = {
  id: '11111111-1111-1111-1111-111111111111',
  name: 'Fresh Toor Dal',
  slug: 'fresh-toor-dal',
  description: 'Freshly packed dal',
  category_id: categoryId,
  category_name: 'Pulses',
  category_slug: 'pulses',
  brand_id: null,
  brand_name: '',
  unit_label: '1 kg',
  mrp_paise: 16000,
  price_paise: 14500,
  stock: 0,
  low_stock_threshold: 10,
  images: [],
  tags: [],
  rating: 0,
  is_active: true,
  is_featured: true,
  variants: [],
  available_stock: 0,
  created_at: '2026-11-25T10:00:00Z',
  updated_at: '2026-11-25T10:00:00Z',
};

describe('StorefrontProductEditor', () => {
  beforeEach(() => vi.unstubAllGlobals());

  it('adds a product from the store view with a simple category and price form', async () => {
    const writes: { method: string; body: unknown }[] = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? 'GET';
        const body = typeof init?.body === 'string' ? JSON.parse(init.body) : null;
        if (method !== 'GET') writes.push({ method, body });
        const json = (payload: unknown) =>
          new Response(JSON.stringify(payload), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        if (url.includes('/api/v1/config')) {
          return json({
            environment: 'test',
            store_name: 'Store',
            store_phone: '',
            store_address: '',
          });
        }
        if (url.includes('/api/v1/admin/catalogue/categories')) {
          return json({
            categories: [{ id: categoryId, name: 'Pulses', slug: 'pulses', parent_id: null }],
          });
        }
        if (url.includes('/api/v1/admin/catalogue/brands')) return json({ brands: [] });
        if (url.includes('/api/v1/admin/catalogue/products') && method === 'POST') {
          return json({ ...createdProduct, ...(body as object) });
        }
        return json({});
      }),
    );

    const user = userEvent.setup();
    const onSaved = vi.fn();
    const onClose = vi.fn();
    renderWithProviders(
      <StorefrontProductEditor open productId={null} onClose={onClose} onSaved={onSaved} />,
    );

    await user.type(await screen.findByRole('textbox', { name: 'Product name' }), 'Fresh Toor Dal');
    await user.selectOptions(screen.getByRole('combobox', { name: 'Category' }), categoryId);
    await user.type(screen.getByRole('spinbutton', { name: 'Selling price (₹)' }), '145');
    await user.type(screen.getByRole('spinbutton', { name: 'MRP (₹)' }), '160');
    await user.type(screen.getByRole('textbox', { name: 'Sold as' }), '1 kg');
    await user.type(screen.getByRole('spinbutton', { name: /Starting stock/ }), '12');
    await user.click(screen.getByRole('button', { name: '+ Add pack' }));
    await user.type(screen.getByRole('textbox', { name: /Pack name/ }), '500 g');
    await user.clear(screen.getByRole('spinbutton', { name: 'Stock available' }));
    await user.type(screen.getByRole('spinbutton', { name: 'Stock available' }), '8');
    await user.click(screen.getByRole('button', { name: 'Add product' }));

    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toMatchObject({
      method: 'POST',
      body: {
        name: 'Fresh Toor Dal',
        category_id: categoryId,
        price_paise: 14500,
        mrp_paise: 16000,
        unit_label: '1 kg',
        stock: 12,
        variants: [
          {
            label: '500 g',
            price_paise: 14500,
            mrp_paise: 16000,
            stock: 8,
            sort_order: 0,
            is_active: true,
          },
        ],
        is_active: true,
        is_featured: true,
      },
    });
    expect(onSaved).toHaveBeenCalledWith('Fresh Toor Dal added on your storefront.');
    expect(onClose).toHaveBeenCalled();
  });
});
