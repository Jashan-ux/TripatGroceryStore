import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import App from '@/App';
import { renderWithProviders } from '@/test/render';

const configResponse = {
  environment: 'test',
  store_name: 'Tripat Pansari MSG Store',
  store_phone: '+91 87089-73386',
  store_address: 'Tripat Pansari MSG Store, near Sabji Mandi, Mandi Dabwali, 125104',
  store_maps_url: 'https://maps.app.goo.gl/test',
  feedback_email: 'tripatinsan029@gmail.com',
  phone_otp_enabled: false,
  turnstile_enabled: false,
  supabase_url: '',
  supabase_anon_key: '',
  vapid_public_key: '',
};

const healthResponse = {
  status: 'ok',
  version: '0.1.0',
  environment: 'test',
  uptime_seconds: 1,
  components: [{ name: 'api', status: 'ok', latency_ms: null }],
};

const emptyPage = { items: [], page: 1, page_size: 24, total: 0, total_pages: 0 };

function json(payload: unknown) {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

function mockFetch() {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes('/api/v1/config')) return json(configResponse);
    if (url.includes('/healthz')) return json(healthResponse);
    if (url.includes('/api/v1/products')) return json(emptyPage);
    if (url.includes('/api/v1/categories')) return json([]);
    if (url.includes('/api/v1/brands')) return json([]);
    if (url.includes('/api/v1/home')) return json({ categories: [], rails: [] });
    return new Response(JSON.stringify({ error: { code: 'not_found', message: 'no' } }), {
      status: 404,
    });
  });
}

describe('App shell', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', mockFetch());
  });

  it('renders the brand, hero banner and store contact from the server', async () => {
    renderWithProviders(<App />);

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(
      /Your family deserves the best/i,
    );
    await waitFor(() => {
      expect(screen.getAllByText('+91 87089-73386').length).toBeGreaterThan(0);
    });
    // The address is server-provided and appears in the footer.
    expect(screen.getAllByText(/near Sabji Mandi, Mandi Dabwali/i).length).toBeGreaterThan(0);
  });

  it('exposes a tap-to-call link and a Maps link', async () => {
    renderWithProviders(<App />);
    const callLinks = await screen.findAllByRole('link', { name: /\+91 87089-73386/ });
    expect(callLinks[0]).toHaveAttribute('href', 'tel:+918708973386');
    expect(screen.getByRole('link', { name: /open in maps/i })).toHaveAttribute(
      'href',
      'https://maps.app.goo.gl/test',
    );
  });

  it('renders the five bottom-nav destinations', () => {
    renderWithProviders(<App />);
    const nav = screen.getAllByRole('navigation', { name: /main navigation/i })[0];
    expect(nav).toBeDefined();
    for (const label of ['Home', 'Category', 'Cart', 'Orders', 'Profile']) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });

  it('sends the search term to /search and shows an empty results state', async () => {
    const user = userEvent.setup();
    renderWithProviders(<App />);

    const search = screen.getByRole('searchbox', { name: /search products/i });
    await user.type(search, 'ghee{Enter}');

    expect(await screen.findByRole('heading', { name: /Results for/i })).toBeInTheDocument();
    expect(screen.getByText(/“ghee”/)).toBeInTheDocument();
    expect(screen.getByText(/No products found/i)).toBeInTheDocument();
  });

  it('shows the 404 page for an unknown route', async () => {
    renderWithProviders(<App />, { route: '/does-not-exist' });
    expect(await screen.findByText('Page not found')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /back to home/i })).toHaveAttribute('href', '/');
  });

  it('keeps the customer cart out of the admin shell and lazy-loads admin', async () => {
    renderWithProviders(<App />, { route: '/admin' });
    expect(await screen.findByRole('heading', { name: 'Analytics' })).toBeInTheDocument();
    // No customer header search, no customer footer links inside admin.
    expect(screen.queryByRole('searchbox')).not.toBeInTheDocument();
    expect(screen.queryByText(/All rights reserved/i)).not.toBeInTheDocument();
  });
});
