import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AdminReturnsPage } from '@/admin/AdminReturnsPage';
import { renderWithProviders } from '@/test/render';
import type { AdminReturnListOut, AdminReturnOut } from '@tripat/api-client';

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

function entry(overrides: Partial<AdminReturnOut> = {}): AdminReturnOut {
  return {
    id: '44444444-4444-4444-4444-444444444444',
    order_id: '22222222-2222-2222-2222-222222222222',
    order_number: 'MSG-261124-AAAAA',
    customer_name: 'Jashan',
    customer_phone: '9876543210',
    status: 'requested',
    reason: 'Ghee leaked',
    requested_at: '2026-11-25T10:00:00Z',
    decided_at: null,
    received_at: null,
    decision_note: '',
    refund_paise: 30000,
    items: [
      {
        order_item_id: '11111111-1111-1111-1111-111111111111',
        name: 'Desi Ghee',
        quantity: 1,
        refund_paise: 30000,
      },
    ],
    ...overrides,
  };
}

function mockFetch(items: AdminReturnOut[]) {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? 'GET';
      calls.push({ url, method, body: init?.body ? JSON.parse(String(init.body)) : null });
      const json = (payload: unknown, status = 200) =>
        new Response(JSON.stringify(payload), {
          status,
          headers: { 'Content-Type': 'application/json' },
        });

      if (url.includes('/api/v1/config')) return json(configResponse);
      if (url.includes('/api/v1/admin/returns/')) {
        const approve = url.endsWith('/decision')
          ? (JSON.parse(String(init?.body)) as { approve: boolean }).approve
          : true;
        return json({
          ...items[0],
          status: url.endsWith('/received')
            ? 'received_credited'
            : approve
              ? 'approved'
              : 'rejected',
        });
      }
      if (url.includes('/api/v1/admin/returns')) {
        const list: AdminReturnListOut = {
          items,
          total: items.length,
          page: 1,
          page_size: 20,
          total_pages: 1,
        };
        return json(list);
      }
      return json({ error: { code: 'not_found', message: 'no' } }, 404);
    }),
  );
  return calls;
}

describe('AdminReturnsPage', () => {
  beforeEach(() => vi.unstubAllGlobals());

  it('asks for the waiting returns by default', async () => {
    const calls = mockFetch([entry()]);
    renderWithProviders(<AdminReturnsPage />, { route: '/admin/returns' });

    expect(await screen.findByText(/MSG-261124-AAAAA/)).toBeInTheDocument();
    expect(screen.getByText('Refund ₹300 to wallet')).toBeInTheDocument();
    const first = calls.find((call) => call.url.includes('/api/v1/admin/returns?'));
    expect(first?.url).toContain('status=requested');
  });

  it('approves a return with the note typed in', async () => {
    const calls = mockFetch([entry()]);
    const user = userEvent.setup();
    renderWithProviders(<AdminReturnsPage />, { route: '/admin/returns' });

    await user.type(await screen.findByLabelText(/note for MSG-261124-AAAAA/i), 'Proof seen');
    await user.click(screen.getByRole('button', { name: /approve/i }));

    await waitFor(() => {
      const post = calls.find((call) => call.url.endsWith('/decision'));
      expect(post?.method).toBe('POST');
      expect(post?.body).toEqual({ approve: true, note: 'Proof seen' });
    });
  });

  it('refuses a return without crediting anything', async () => {
    const calls = mockFetch([entry()]);
    const user = userEvent.setup();
    renderWithProviders(<AdminReturnsPage />, { route: '/admin/returns' });

    await user.click(await screen.findByRole('button', { name: /refuse/i }));

    await waitFor(() => {
      const post = calls.find((call) => call.url.endsWith('/decision'));
      expect(post?.body).toMatchObject({ approve: false });
    });
    expect(calls.some((call) => call.url.endsWith('/received'))).toBe(false);
  });

  it('credits only from the approved tab, via "goods received"', async () => {
    const calls = mockFetch([entry({ status: 'approved' })]);
    const user = userEvent.setup();
    renderWithProviders(<AdminReturnsPage />, { route: '/admin/returns' });

    // Approve/refuse are not offered again once a decision is made.
    expect(screen.queryByRole('button', { name: /^approve$/i })).not.toBeInTheDocument();
    await user.click(
      await screen.findByRole('button', { name: /goods received · credit wallet/i }),
    );

    await waitFor(() => {
      const post = calls.find((call) => call.url.endsWith('/received'));
      expect(post?.method).toBe('POST');
    });
  });
});
