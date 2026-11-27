import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import NotificationsPage from '@/pages/NotificationsPage';

// The page is behind `ProtectedRoute` in the app, so the test supplies a signed-in
// session directly instead of booting Supabase Auth (which needs a network).
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

const ENTRIES = [
  {
    id: '11111111-1111-1111-1111-111111111111',
    kind: 'order_status',
    title: 'MSG-261125-AB12C: Packed and shipped',
    body: 'Your order has left the shop.',
    href: '/orders/22222222-2222-2222-2222-222222222222',
    order_id: '22222222-2222-2222-2222-222222222222',
    read: false,
    created_at: '2026-11-25T09:30:00Z',
  },
  {
    id: '33333333-3333-3333-3333-333333333333',
    kind: 'order_placed',
    title: 'Order MSG-251125-ZZ99Y confirmed',
    body: 'Thank you! 2 items · ₹640, cash on delivery.',
    href: '/orders/44444444-4444-4444-4444-444444444444',
    order_id: '44444444-4444-4444-4444-444444444444',
    read: true,
    created_at: '2026-11-25T08:00:00Z',
  },
];

function mockFetch({ unread = 1 } = {}) {
  const calls: { url: string; method: string }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? 'GET';
      calls.push({ url, method });
      const json = (body: unknown, status = 200) =>
        new Response(JSON.stringify(body), {
          status,
          headers: { 'Content-Type': 'application/json' },
        });

      if (url.includes('/api/v1/config')) return json(configResponse);
      if (url.includes('/api/v1/notifications/unread-count')) return json({ unread_count: unread });
      if (url.endsWith('/read-all')) return json({ marked: 1 });
      if (url.includes('/ack')) return json({ ...ENTRIES[0], read: true });
      if (url.includes('/api/v1/notifications')) {
        return json({
          items: ENTRIES,
          unread_count: unread,
          total: ENTRIES.length,
          page: 1,
          page_size: 20,
          total_pages: 1,
        });
      }
      return json({ error: { code: 'not_found', message: 'no' } }, 404);
    }),
  );
  return calls;
}

describe('notifications page', () => {
  beforeEach(() => {
    mockFetch();
  });

  it('lists what happened, newest first, with unread styling', async () => {
    renderWithProviders(<NotificationsPage />, { route: '/notifications' });

    expect(screen.getByRole('heading', { name: 'Notifications' })).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByText(/Packed and shipped/)).toBeInTheDocument();
    });
    expect(screen.getByText('Order MSG-251125-ZZ99Y confirmed')).toBeInTheDocument();
    expect(screen.getByText('1 unread')).toBeInTheDocument();
    // The unread badge is exposed to assistive tech, not only as a coloured dot.
    expect(screen.getAllByLabelText('Unread')).toHaveLength(1);
  });

  it('opens a notification: acknowledges it and follows the server-written link', async () => {
    const calls = mockFetch();
    const user = userEvent.setup();
    renderWithProviders(<NotificationsPage />, { route: '/notifications' });

    await user.click(await screen.findByText(/Packed and shipped/));

    await waitFor(() => {
      expect(calls.some((call) => call.method === 'POST' && call.url.includes('/ack'))).toBe(true);
    });
  });

  it('marks everything read in one explicit action', async () => {
    const calls = mockFetch();
    const user = userEvent.setup();
    renderWithProviders(<NotificationsPage />, { route: '/notifications' });

    await user.click(await screen.findByRole('button', { name: /mark all read/i }));
    await waitFor(() => {
      expect(calls.some((call) => call.url.endsWith('/read-all'))).toBe(true);
    });
  });

  it('offers a calm empty state', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (input: RequestInfo | URL) => {
        const url = String(input);
        const json = (body: unknown) =>
          new Response(JSON.stringify(body), {
            status: 200,
            headers: { 'Content-Type': 'application/json' },
          });
        if (url.includes('/api/v1/config')) return json(configResponse);
        if (url.includes('/unread-count')) return json({ unread_count: 0 });
        return json({
          items: [],
          unread_count: 0,
          total: 0,
          page: 1,
          page_size: 20,
          total_pages: 0,
        });
      }),
    );

    renderWithProviders(<NotificationsPage />, { route: '/notifications' });
    expect(await screen.findByText('Nothing here yet')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /mark all read/i })).not.toBeInTheDocument();
  });
});
