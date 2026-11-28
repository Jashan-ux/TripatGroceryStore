import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';

import App from '@/App';
import { AuthContext, type AuthContextValue } from '@/features/auth/context';
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

function renderAsRole(role: 'admin' | 'customer', route = '/admin') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  const auth = {
    status: 'authenticated',
    session: null,
    user: null,
    profile: { role } as AuthContextValue['profile'],
    isAdmin: role === 'admin',
    authAvailable: true,
    needsPhone: false,
    error: null,
    refreshProfile: async () => undefined,
    signInWithPassword: async () => ({ role }) as NonNullable<AuthContextValue['profile']>,
    signUpWithPassword: async () => ({ needsEmailConfirmation: false }),
    signInWithGoogle: async () => undefined,
    sendPasswordReset: async () => undefined,
    signOut: async () => undefined,
  } satisfies AuthContextValue;
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[route]}>
        <AuthContext.Provider value={auth}>
          <App />
        </AuthContext.Provider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

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
    if (url.includes('/api/v1/admin/catalogue/products')) {
      return json({ items: [], total: 0, page: 1, page_size: 20, total_pages: 0 });
    }
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
    window.sessionStorage.clear();
    vi.stubGlobal('fetch', mockFetch());
  });

  it('renders the brand, hero banner and store contact from the server', async () => {
    renderWithProviders(<App />);

    expect(await screen.findByRole('heading', { level: 1 })).toHaveTextContent(
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

  it('renders the five bottom-nav destinations', async () => {
    renderWithProviders(<App />);
    const nav = (await screen.findAllByRole('navigation', { name: /main navigation/i }))[0];
    expect(nav).toBeDefined();
    for (const label of ['Home', 'Category', 'Cart', 'Orders', 'Profile']) {
      expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    }
  });

  it('sends the search term to /search and shows an empty results state', async () => {
    const user = userEvent.setup();
    renderWithProviders(<App />);

    const search = await screen.findByRole('searchbox', { name: /search products/i });
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
    renderAsRole('admin');
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Cart' })).not.toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Preview storefront as a customer' })).toHaveAttribute(
      'href',
      '/?preview=1',
    );
    expect(screen.getByRole('searchbox', { name: 'Find a product to edit' })).toBeInTheDocument();
    expect(
      screen.getAllByRole('navigation', { name: 'Merchant navigation' }).length,
    ).toBeGreaterThan(0);
    expect(screen.queryByText(/All rights reserved/i)).not.toBeInTheDocument();
  });

  it('provides a read-only preview with an exit back to the console', async () => {
    const user = userEvent.setup();
    renderAsRole('admin', '/?preview=1');

    expect(await screen.findByText('Preview mode')).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Cart' })).not.toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Exit' }));
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
  });

  it('keeps signed-in customers out of the admin console', async () => {
    renderAsRole('customer');
    expect(
      await screen.findByRole('heading', { name: /Your family deserves the best/i }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Dashboard' })).not.toBeInTheDocument();
  });
});
