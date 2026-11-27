import type { DeliveryOrderListOut, DeliveryOrderOut } from '@tripat/api-client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { DeliveryPage } from '@/delivery/DeliveryPage';
import { AuthContext, type AuthContextValue } from '@/features/auth/context';

const order: DeliveryOrderOut = {
  id: 'order-1',
  order_number: 'MSG-2026-001',
  status: 'shipped',
  payment_method: 'cod',
  payment_status: 'pending',
  total_paise: 7900,
  item_count: 2,
  customer_name: 'Asha Sharma',
  customer_phone: '9876543210',
  address: {
    label: 'Home',
    recipient_name: 'Asha Sharma',
    phone: '9876543210',
    line1: 'House 12, Main Road',
    line2: '',
    landmark: 'Near market',
    pincode: '125104',
    city: 'Mandi Dabwali',
    state: 'Haryana',
  },
  items: [
    {
      name: 'Mustard oil',
      unit_label: '1 L',
      variant_label: '',
      quantity: 2,
      line_total_paise: 7900,
    },
  ],
  out_for_delivery_at: null,
  delivered_at: null,
};

const auth = {
  status: 'authenticated',
  session: null,
  user: null,
  profile: {
    id: 'driver-1',
    name: 'Delivery Worker',
    email: 'driver@example.com',
    phone: null,
    role: 'delivery',
    referral_code: '',
    lifetime_spend_paise: 0,
    loyalty_tier: 'none',
    notification_prefs: {},
    has_phone: false,
    created_at: '2026-11-25T00:00:00Z',
  },
  isAdmin: false,
  authAvailable: true,
  needsPhone: false,
  error: null,
  refreshProfile: vi.fn(async () => {}),
  signInWithPassword: vi.fn(),
  signUpWithPassword: vi.fn(),
  signInWithGoogle: vi.fn(),
  sendPasswordReset: vi.fn(),
  signOut: vi.fn(async () => {}),
} as unknown as AuthContextValue;

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <AuthContext.Provider value={auth}>
          <DeliveryPage />
        </AuthContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function installFetch(initial: DeliveryOrderOut[] = [order]) {
  const calls: { url: string; method: string }[] = [];
  let current = initial;
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? 'GET';
      calls.push({ url, method });
      const json = (payload: unknown, status = 200) =>
        new Response(JSON.stringify(payload), {
          status,
          headers: { 'Content-Type': 'application/json' },
        });
      if (url.includes('/delivery/orders/') && method === 'POST') {
        const isDelivered = url.endsWith('/delivered');
        current = [
          {
            ...order,
            status: isDelivered ? 'delivered' : 'out_for_delivery',
            payment_status: isDelivered ? 'paid' : 'pending',
            out_for_delivery_at: '2026-11-25T10:00:00Z',
            delivered_at: isDelivered ? '2026-11-25T11:00:00Z' : null,
          },
        ];
        return json(current[0]);
      }
      if (url.endsWith('/delivery/orders')) {
        return json({ items: current, total: current.length } satisfies DeliveryOrderListOut);
      }
      return json({ error: { code: 'not_found', message: 'No route' } }, 404);
    }),
  );
  return calls;
}

afterEach(() => vi.unstubAllGlobals());

describe('DeliveryPage', () => {
  it('shows the assigned order and moves it forward with idempotent actions', async () => {
    const calls = installFetch();
    const user = userEvent.setup();
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    renderPage();

    expect(await screen.findByText('MSG-2026-001')).toBeVisible();
    expect(screen.getAllByText('Asha Sharma')).toHaveLength(2);
    expect(screen.getByText(/House 12, Main Road/)).toBeVisible();
    expect(screen.getByText(/Mustard oil/)).toBeVisible();
    expect(screen.getAllByText('₹79')).toHaveLength(2);

    await user.click(screen.getByRole('button', { name: /mark out for delivery/i }));
    await screen.findByRole('button', { name: /mark delivered/i });
    await user.click(screen.getByRole('button', { name: /mark delivered/i }));

    await waitFor(() => expect(calls.filter((call) => call.method === 'POST')).toHaveLength(2));
    expect(calls.some((call) => call.url.endsWith('/out-for-delivery'))).toBe(true);
    expect(calls.some((call) => call.url.endsWith('/delivered'))).toBe(true);
    expect(confirmSpy).toHaveBeenCalledOnce();
  });

  it('renders an honest empty state', async () => {
    installFetch([]);
    renderPage();
    expect(await screen.findByText('No active deliveries assigned')).toBeVisible();
  });

  it('shows an error and retry control when assigned orders fail to load', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              error: { code: 'unavailable', message: 'Delivery service offline' },
            }),
            { status: 503, headers: { 'Content-Type': 'application/json' } },
          ),
      ),
    );
    renderPage();
    expect(await screen.findByText(/Delivery service offline/)).toBeVisible();
    expect(screen.getByRole('button', { name: 'Try again' })).toBeVisible();
  });
});
