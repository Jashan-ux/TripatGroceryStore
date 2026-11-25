import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('@/features/auth/useAuth', () => ({
  useAuth: () => ({
    status: 'authenticated',
    profile: { id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa', name: 'Jashan', phone: '9876543210' },
    isAdmin: false,
    authAvailable: true,
    signOut: async () => undefined,
    refreshProfile: async () => undefined,
  }),
}));

import { ReturnPanel } from '@/components/orders/ReturnPanel';
import { renderWithProviders } from '@/test/render';
import type { OrderOut } from '@tripat/api-client';

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

const ITEM_ID = '11111111-1111-1111-1111-111111111111';

function order(overrides: Partial<OrderOut> = {}): OrderOut {
  return {
    id: '22222222-2222-2222-2222-222222222222',
    order_number: 'MSG-261124-AAAAA',
    status: 'delivered',
    placed_at: '2026-11-24T09:00:00Z',
    deliver_by: '2026-11-25',
    delivery_days: 1,
    customer_name: 'Jashan',
    customer_phone: '9876543210',
    customer_note: '',
    subtotal_paise: 60000,
    delivery_fee_paise: 0,
    discount_paise: 0,
    discount_reason: '',
    wallet_paise: 0,
    total_paise: 60000,
    item_count: 2,
    payment_method: 'cod',
    payment_status: 'pending',
    cancelled_at: null,
    cancelled_reason: '',
    address: {
      recipient_name: 'Jashan',
      phone: '9876543210',
      line1: '12 Gali 3',
      line2: '',
      landmark: '',
      city: 'Mandi Dabwali',
      state: 'Haryana',
      pincode: '125104',
    },
    items: [
      {
        id: ITEM_ID,
        product_id: '33333333-3333-3333-3333-333333333333',
        name: 'Desi Ghee',
        unit_label: '1 kg',
        variant_label: '',
        image_url: '',
        quantity: 2,
        unit_price_paise: 30000,
        line_total_paise: 60000,
      },
    ],
    events: [],
    ...overrides,
  } as OrderOut;
}

function mockFetch({ existing = [] as unknown[] } = {}) {
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
      if (url.includes('/api/v1/returns')) return json({ returns: existing });
      if (url.includes('/return'))
        return json(
          {
            id: '44444444-4444-4444-4444-444444444444',
            order_id: order().id,
            order_number: order().order_number,
            status: 'requested',
            reason: 'Damaged',
            requested_at: '2026-11-25T10:00:00Z',
            decided_at: null,
            received_at: null,
            decision_note: '',
            refund_paise: 60000,
            items: [
              {
                order_item_id: ITEM_ID,
                name: 'Desi Ghee',
                quantity: 2,
                refund_paise: 60000,
              },
            ],
          },
          201,
        );
      return json({ error: { code: 'not_found', message: 'no' } }, 404);
    }),
  );
  return calls;
}

describe('ReturnPanel', () => {
  beforeEach(() => vi.unstubAllGlobals());

  it('stays out of the way until the order has arrived', () => {
    mockFetch();
    renderWithProviders(<ReturnPanel order={order({ status: 'shipped' })} />);
    expect(screen.queryByText('Returns')).not.toBeInTheDocument();
  });

  it('promises the wallet credit only after approval and receipt', async () => {
    mockFetch();
    const user = userEvent.setup();
    renderWithProviders(<ReturnPanel order={order()} />);

    await user.click(await screen.findByRole('button', { name: /return an item/i }));
    expect(screen.getByText(/once we approve the return/i)).toBeInTheDocument();
  });

  it('sends quantities and the reason to the order', async () => {
    const calls = mockFetch();
    const user = userEvent.setup();
    renderWithProviders(<ReturnPanel order={order()} />);

    await user.click(await screen.findByRole('button', { name: /return an item/i }));
    await user.click(screen.getByRole('button', { name: 'More Desi Ghee' }));
    await user.type(screen.getByLabelText(/what went wrong/i), 'Damaged');
    // ₹300 a unit × 1 chosen.
    expect(screen.getByText('Up to ₹300 back to your wallet.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /request return/i }));

    await waitFor(() => {
      const post = calls.find((call) => call.method === 'POST');
      expect(post?.url).toContain(`/api/v1/orders/${order().id}/return`);
      expect(post?.body).toEqual({
        items: [{ order_item_id: ITEM_ID, quantity: 1 }],
        reason: 'Damaged',
      });
    });
  });

  it('lists an in-flight return instead of offering a second one', async () => {
    mockFetch({
      existing: [
        {
          id: '44444444-4444-4444-4444-444444444444',
          order_id: order().id,
          order_number: order().order_number,
          status: 'approved',
          reason: 'Damaged',
          requested_at: '2026-11-25T10:00:00Z',
          decided_at: '2026-11-25T11:00:00Z',
          received_at: null,
          decision_note: 'Send it back',
          refund_paise: 30000,
          items: [{ order_item_id: ITEM_ID, name: 'Desi Ghee', quantity: 1, refund_paise: 30000 }],
        },
      ],
    });
    renderWithProviders(<ReturnPanel order={order()} />);

    expect(await screen.findByText(/approved — we are waiting for the items/i)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /return an item/i })).not.toBeInTheDocument();
  });
});
