import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AdminFeedbackPage } from '@/admin/AdminFeedbackPage';
import { AdminOffersPage } from '@/admin/AdminOffersPage';
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

const message = {
  id: 'dddddddd-dddd-dddd-dddd-dddddddddddd',
  name: 'Ramesh Kumar',
  phone: '9876543210',
  email: '',
  kind: 'order',
  message: 'The atta packet was torn on delivery.',
  status: 'new',
  read_at: null,
  created_at: '2026-11-25T09:00:00Z',
  customer_name: '',
};

interface Call {
  url: string;
  method: string;
  body: unknown;
}

function mockFetch(handlers: Record<string, (call: Call) => unknown>) {
  const calls: Call[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? 'GET';
      const call: Call = {
        url,
        method,
        body: typeof init?.body === 'string' ? JSON.parse(init.body) : null,
      };
      calls.push(call);
      const json = (payload: unknown, status = 200) =>
        new Response(JSON.stringify(payload), {
          status,
          headers: { 'Content-Type': 'application/json' },
        });
      if (url.includes('/api/v1/config')) return json(configResponse);
      for (const [fragment, handler] of Object.entries(handlers)) {
        if (url.includes(fragment)) return json(handler(call));
      }
      return json({ error: { code: 'not_found', message: 'no' } }, 404);
    }),
  );
  return calls;
}

describe('AdminOffersPage', () => {
  beforeEach(() => vi.unstubAllGlobals());

  it('sends an offer to one tier and reports who it reached', async () => {
    const calls = mockFetch({
      '/api/v1/admin/offers': (call) =>
        call.method === 'POST'
          ? {
              id: 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
              title: 'Gold members: 10% off ghee',
              body: '',
              href: '/',
              audience: 'gold',
              is_active: true,
              expires_at: null,
              recipients: 3,
              emails_queued: 2,
              push_queued: 1,
              sent_at: '2026-11-25T10:00:00Z',
              created_at: '2026-11-25T10:00:00Z',
            }
          : { items: [], total: 0, page: 1, page_size: 20, total_pages: 1 },
      '/api/v1/offers/current': () => ({ offer: null }),
    });
    const user = userEvent.setup();
    renderWithProviders(<AdminOffersPage />, { route: '/admin/offers' });

    await user.type(await screen.findByLabelText('Title'), 'Gold members: 10% off ghee');
    await user.selectOptions(screen.getByLabelText('Who hears it'), 'gold');
    await user.click(screen.getByRole('button', { name: /send offer/i }));

    await waitFor(() => {
      const post = calls.find((call) => call.method === 'POST');
      expect(post?.body).toMatchObject({ title: 'Gold members: 10% off ghee', audience: 'gold' });
      // The expiry is a real date, not the word "7".
      expect(String((post?.body as { expires_at: string }).expires_at)).toMatch(/^\d{4}-/);
    });
    expect(
      await screen.findByText(/sent to 3 customers — 2 emails queued · 1 push device targeted/i),
    ).toBeInTheDocument();
  });

  it('shows what is live on the storefront right now', async () => {
    mockFetch({
      '/api/v1/offers/current': () => ({
        offer: {
          id: 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
          title: 'Diwali hours: open till 9pm',
          body: '',
          href: '/',
          audience: 'all',
          is_active: true,
          expires_at: null,
          recipients: 12,
          emails_queued: 9,
          sent_at: '2026-11-25T10:00:00Z',
          created_at: '2026-11-25T10:00:00Z',
        },
      }),
      '/api/v1/admin/offers': () => ({
        items: [],
        total: 0,
        page: 1,
        page_size: 20,
        total_pages: 1,
      }),
    });
    renderWithProviders(<AdminOffersPage />, { route: '/admin/offers' });
    expect(await screen.findByText(/on the storefront now/i)).toBeInTheDocument();
    expect(screen.getByText(/Diwali hours: open till 9pm/)).toBeInTheDocument();
  });
});

describe('AdminFeedbackPage', () => {
  beforeEach(() => vi.unstubAllGlobals());

  it('lists new messages with the customer’s number to call back', async () => {
    const calls = mockFetch({
      '/api/v1/admin/feedback': () => ({
        items: [message],
        total: 1,
        page: 1,
        page_size: 25,
        total_pages: 1,
      }),
    });
    renderWithProviders(<AdminFeedbackPage />, { route: '/admin/feedback' });

    expect(await screen.findByText('Ramesh Kumar')).toBeInTheDocument();
    expect(screen.getByText(/atta packet was torn/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '9876543210' })).toHaveAttribute(
      'href',
      'tel:9876543210',
    );
    // Default tab is the unread inbox.
    expect(calls.find((call) => call.url.includes('/admin/feedback?'))?.url).toContain(
      'status=new',
    );
  });

  it('marks a message read with an explicit tap', async () => {
    const calls = mockFetch({
      '/api/v1/admin/feedback/': (call) =>
        call.method === 'POST'
          ? { ...message, status: 'read', read_at: '2026-11-25T11:00:00Z' }
          : null,
      '/api/v1/admin/feedback': () => ({
        items: [message],
        total: 1,
        page: 1,
        page_size: 25,
        total_pages: 1,
      }),
    });
    const user = userEvent.setup();
    renderWithProviders(<AdminFeedbackPage />, { route: '/admin/feedback' });

    await user.click(await screen.findByRole('button', { name: /mark read/i }));

    await waitFor(() => {
      const post = calls.find((call) => call.method === 'POST');
      expect(post?.url).toContain(`/api/v1/admin/feedback/${message.id}/read`);
    });
  });
});
