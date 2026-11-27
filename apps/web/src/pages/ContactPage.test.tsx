import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ContactPage from '@/pages/ContactPage';
import { renderWithProviders } from '@/test/render';

const configResponse = {
  environment: 'test',
  store_name: 'Tripat Pansari MSG Store',
  store_phone: '+91 87089-73386',
  store_address: 'near Sabji Mandi, Mandi Dabwali, 125104',
  store_maps_url: 'https://maps.app.goo.gl/example',
  feedback_email: 'store@example.com',
  phone_otp_enabled: false,
  turnstile_enabled: false,
  supabase_url: '',
  supabase_anon_key: '',
  vapid_public_key: '',
};

interface Call {
  url: string;
  method: string;
  body: unknown;
}

function mockFetch(options: { failFeedback?: boolean } = {}) {
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
      if (url.endsWith('/api/v1/feedback')) {
        if (options.failFeedback) {
          return json(
            { error: { code: 'unavailable', message: 'Please call the shop instead.' } },
            503,
          );
        }
        return json(
          {
            id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
            name: 'Ramesh',
            phone: '9876543210',
            email: '',
            kind: 'order',
            message: 'Packet was torn',
            status: 'new',
            read_at: null,
            created_at: '2026-11-25T10:00:00Z',
            customer_name: '',
          },
          201,
        );
      }
      return json({ error: { code: 'not_found', message: 'no' } }, 404);
    }),
  );
  return calls;
}

describe('ContactPage', () => {
  beforeEach(() => vi.unstubAllGlobals());

  it('shows a tappable number, the address, and a Maps link from the server', async () => {
    mockFetch();
    renderWithProviders(<ContactPage />, { route: '/contact' });

    const phone = await screen.findByRole('link', { name: '+91 87089-73386' });
    expect(phone).toHaveAttribute('href', 'tel:+918708973386');
    expect(screen.getByText(/Mandi Dabwali/)).toBeInTheDocument();
    const maps = screen.getByRole('link', { name: /open in maps/i });
    expect(maps).toHaveAttribute('href', configResponse.store_maps_url);
    expect(maps).toHaveAttribute('rel', expect.stringContaining('noopener'));
  });

  it('sends the message and thanks the customer', async () => {
    const calls = mockFetch();
    const user = userEvent.setup();
    renderWithProviders(<ContactPage />, { route: '/contact' });

    await user.type(screen.getByLabelText('Your name'), 'Ramesh');
    await user.type(screen.getByLabelText('Phone'), '9876543210');
    await user.selectOptions(screen.getByLabelText('What is this about?'), 'order');
    await user.type(screen.getByLabelText('Message'), 'Packet was torn');
    await user.click(screen.getByRole('button', { name: /send message/i }));

    expect(await screen.findByText(/your message has reached the shop/i)).toBeInTheDocument();
    const post = calls.find((call) => call.url.endsWith('/api/v1/feedback'));
    expect(post?.method).toBe('POST');
    expect(post?.body).toMatchObject({
      name: 'Ramesh',
      phone: '9876543210',
      kind: 'order',
      message: 'Packet was torn',
    });
  });

  it('says so plainly when the message could not be stored', async () => {
    mockFetch({ failFeedback: true });
    const user = userEvent.setup();
    renderWithProviders(<ContactPage />, { route: '/contact' });

    await user.type(screen.getByLabelText('Message'), 'Hello there');
    await user.click(screen.getByRole('button', { name: /send message/i }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Please call the shop instead.');
  });

  it('does not offer an empty submit — the message field is required', async () => {
    mockFetch();
    renderWithProviders(<ContactPage />, { route: '/contact' });
    await waitFor(() => expect(screen.getByLabelText('Message')).toBeRequired());
  });
});
