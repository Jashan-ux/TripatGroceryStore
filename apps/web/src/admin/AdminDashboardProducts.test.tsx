import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AdminDashboardProducts } from '@/admin/AdminDashboardProducts';
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

const product = {
  id: '11111111-1111-1111-1111-111111111111',
  name: 'Desi Ghee 1 L',
  slug: 'desi-ghee-1-l',
  description: '',
  category_id: '99999999-9999-9999-9999-999999999999',
  category_name: 'Ghee & Oils',
  category_slug: 'ghee-oils',
  brand_id: null,
  brand_name: 'MSG',
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

describe('AdminDashboardProducts', () => {
  beforeEach(() => vi.unstubAllGlobals());

  it('edits product details inline on the dashboard and confirms the saved change', async () => {
    const calls: { method: string; body: unknown }[] = [];
    let saved = product;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
        const url = String(input);
        const method = init?.method ?? 'GET';
        const body = typeof init?.body === 'string' ? JSON.parse(init.body) : null;
        calls.push({ method, body });
        const json = (payload: unknown) =>
          new Response(JSON.stringify(payload), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        if (url.includes('/api/v1/config')) return json(configResponse);
        if (url.includes('/api/v1/admin/catalogue/products') && method === 'PATCH') {
          saved = { ...saved, ...(body as object) };
          return json(saved);
        }
        if (url.includes('/api/v1/admin/catalogue/products')) {
          return json({ items: [saved], total: 1, page: 1, page_size: 20, total_pages: 1 });
        }
        return json({ error: { code: 'not_found', message: 'Not found' } });
      }),
    );

    const user = userEvent.setup();
    renderWithProviders(<AdminDashboardProducts />, { route: '/admin' });

    expect(await screen.findByText('Desi Ghee 1 L')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Edit Desi Ghee 1 L on dashboard' }));
    const price = screen.getByRole('spinbutton', { name: 'Selling price (₹)' });
    await user.clear(price);
    await user.type(price, '650');
    await user.click(screen.getByRole('button', { name: 'Save product' }));

    await waitFor(() => {
      expect(calls.some((call) => call.method === 'PATCH' && call.body !== null)).toBe(true);
    });
    const patch = calls.find((call) => call.method === 'PATCH');
    expect(patch?.body).toMatchObject({
      name: 'Desi Ghee 1 L',
      price_paise: 65000,
      mrp_paise: 66000,
      unit_label: '1 L',
      is_active: true,
    });
    expect(await screen.findByRole('status')).toHaveTextContent('Desi Ghee 1 L saved.');
  });
});
