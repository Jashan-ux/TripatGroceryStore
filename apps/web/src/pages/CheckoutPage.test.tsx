import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import type { QuoteOut } from '@tripat/api-client';
import CheckoutPage from '@/pages/CheckoutPage';
import { CART_STORAGE_KEY } from '@/features/cart/storage';
import { renderWithProviders } from '@/test/render';

// Checkout is for signed-in customers (addresses + a phone number for the rider).
vi.mock('@/features/auth/useAuth', () => ({
  useAuth: () => ({
    status: 'authenticated',
    profile: {
      id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
      name: 'Jashan',
      phone: '9876543210',
      email: 'jashan@example.com',
    },
    isAdmin: false,
    authAvailable: true,
    signOut: async () => undefined,
    refreshProfile: async () => undefined,
  }),
}));

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

const ADDRESS = {
  id: 'dddddddd-dddd-dddd-dddd-dddddddddddd',
  label: 'Home',
  recipient_name: 'Jashan',
  phone: '9876543210',
  line1: '12 Gali 3',
  line2: '',
  landmark: '',
  city: 'Mandi Dabwali',
  state: 'Haryana',
  pincode: '125104',
  is_default: true,
  latitude: null,
  longitude: null,
};

const cart = {
  lines: [
    {
      productId: '11111111-1111-1111-1111-111111111111',
      variantId: null,
      slug: 'ghee',
      name: 'Desi Ghee',
      unitLabel: '1 kg',
      variantLabel: '',
      imageUrl: null,
      pricePaise: 60000,
      maxQuantity: 5,
      quantity: 1,
    },
  ],
};

function quote(overrides: Partial<QuoteOut> = {}): QuoteOut {
  return {
    lines: [
      {
        product_id: cart.lines[0]!.productId,
        variant_id: null,
        slug: 'ghee',
        name: 'Desi Ghee',
        unit_label: '1 kg',
        variant_label: '',
        image_url: '',
        quantity: 1,
        unit_price_paise: 60000,
        mrp_paise: 60000,
        line_total_paise: 60000,
        available_stock: 5,
        in_stock: true,
        issue: null,
      },
    ],
    subtotal_paise: 60000,
    delivery_fee_paise: 0,
    discount_paise: 0,
    discount_reason: '',
    wallet_available_paise: 0,
    wallet_applied_paise: 0,
    payable_before_wallet_paise: 60000,
    total_paise: 60000,
    item_count: 1,
    minimum_order_paise: 50000,
    shortfall_paise: 0,
    deliver_by: '2026-11-26',
    delivery_days: 1,
    pincode: '125104',
    pincode_serviceable: true,
    blocking_issues: [],
    can_checkout: true,
    ...overrides,
  };
}

/** Quote that answers the wallet question the way the API would. */
function walletAwareQuote(balance: number, overrides: Partial<QuoteOut> = {}): QuoteOut {
  return quote({
    wallet_available_paise: balance,
    wallet_applied_paise: overrides.wallet_applied_paise ?? 0,
    ...overrides,
  });
}

type MockAddress = typeof ADDRESS & { created_at?: string };

function mockFetch(
  respond: (body: unknown) => QuoteOut,
  options: {
    initialAddresses?: MockAddress[];
    failAddressReloadAfterSave?: boolean;
    failAddressSave?: boolean;
  } = {},
) {
  const calls: { url: string; method: string; body: unknown; headers: Headers }[] = [];
  let savedAddresses: MockAddress[] = [...(options.initialAddresses ?? [ADDRESS])];
  let addressSaveCount = 0;
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? 'GET';
      const body = init?.body ? JSON.parse(String(init.body)) : null;
      calls.push({ url, method, body, headers: new Headers(init?.headers) });
      const json = (payload: unknown, status = 200) =>
        new Response(JSON.stringify(payload), {
          status,
          headers: { 'Content-Type': 'application/json' },
        });

      if (url.includes('/api/v1/config')) return json(configResponse);
      if (url.includes('/api/v1/checkout/quote')) return json(respond(body));
      if (url.includes('/api/v1/addresses')) {
        if (method === 'GET') {
          if (options.failAddressReloadAfterSave && addressSaveCount > 0) {
            return json(
              { error: { code: 'temporarily_unavailable', message: 'Address refresh failed.' } },
              503,
            );
          }
          return json(savedAddresses);
        }
        if (method === 'POST' || method === 'PUT') {
          addressSaveCount += 1;
          if (options.failAddressSave) {
            return json(
              {
                error: { code: 'database_unavailable', message: 'We could not save that address.' },
              },
              503,
            );
          }
          const id =
            method === 'POST'
              ? 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee'
              : (url.split('/').at(-1) ?? ADDRESS.id);
          const saved = {
            ...(body as Record<string, unknown>),
            id,
            created_at: '2026-11-25T09:30:00Z',
          } as MockAddress;
          savedAddresses =
            method === 'POST'
              ? [...savedAddresses, saved]
              : savedAddresses.map((address) => (address.id === id ? saved : address));
          return json(saved, method === 'POST' ? 201 : 200);
        }
      }
      if (url.includes('/api/v1/orders'))
        return json({ id: '99999999-9999-9999-9999-999999999999' }, 201);
      return json({ error: { code: 'not_found', message: 'no' } }, 404);
    }),
  );
  return calls;
}

const quoteBodies = (calls: { url: string; body: unknown }[]) =>
  calls.filter((call) => call.url.includes('/api/v1/checkout/quote')).map((call) => call.body);

describe('CheckoutPage wallet and addresses', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
    localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(cart));
  });

  it('persists a new address and shows it even if the follow-up refresh fails', async () => {
    const calls = mockFetch(() => quote(), {
      initialAddresses: [],
      failAddressReloadAfterSave: true,
    });
    const user = userEvent.setup();
    renderWithProviders(<CheckoutPage />, { route: '/checkout' });

    await user.type(await screen.findByLabelText('Full name'), 'Jashan Kumar');
    await user.type(screen.getByLabelText('Mobile number'), '9876543210');
    await user.type(screen.getByLabelText('House / flat, street'), '12 Gali 3 Main Road');
    await user.type(screen.getByLabelText('Pincode'), '122001');
    await user.click(screen.getByRole('button', { name: 'Save address' }));

    await waitFor(() => {
      const saveCall = calls.find(
        (call) => call.url.endsWith('/api/v1/addresses') && call.method === 'POST',
      );
      expect(saveCall?.body).toMatchObject({
        recipient_name: 'Jashan Kumar',
        phone: '9876543210',
        line1: '12 Gali 3 Main Road',
        pincode: '122001',
      });
    });
    expect(await screen.findByText('Jashan Kumar')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /add another address/i })).toBeInTheDocument();
  });

  it('shows a server failure and keeps Save Address available for retry', async () => {
    const calls = mockFetch(() => quote(), { initialAddresses: [], failAddressSave: true });
    const user = userEvent.setup();
    renderWithProviders(<CheckoutPage />, { route: '/checkout' });

    await user.type(await screen.findByLabelText('Full name'), 'Jashan Kumar');
    await user.type(screen.getByLabelText('Mobile number'), '9876543210');
    await user.type(screen.getByLabelText('House / flat, street'), '12 Gali 3 Main Road');
    await user.type(screen.getByLabelText('Pincode'), '122001');
    await user.click(screen.getByRole('button', { name: 'Save address' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('We could not save that address.');
    expect(
      calls.filter((call) => call.method === 'POST' && call.url.endsWith('/api/v1/addresses')),
    ).toHaveLength(1);
    expect(screen.getByRole('button', { name: 'Save address' })).toBeEnabled();
  });

  it('explains client-side validation instead of silently ignoring the submit', async () => {
    const calls = mockFetch(() => quote(), { initialAddresses: [] });
    const user = userEvent.setup();
    renderWithProviders(<CheckoutPage />, { route: '/checkout' });

    await user.click(await screen.findByRole('button', { name: 'Save address' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Please check the highlighted fields and try again.',
    );
    expect(screen.getByText('Who should we ask for?')).toBeInTheDocument();
    expect(
      calls.some((call) => call.method === 'POST' && call.url.endsWith('/api/v1/addresses')),
    ).toBe(false);
  });

  it('asks for the balance first, without spending it', async () => {
    const calls = mockFetch(() => walletAwareQuote(25000));
    renderWithProviders(<CheckoutPage />, { route: '/checkout' });

    await waitFor(() => expect(quoteBodies(calls).length).toBeGreaterThan(0));
    // The probe asks high so the server can report the balance; it applies nothing.
    const [first] = quoteBodies(calls);
    expect(first).toMatchObject({ use_wallet_paise: 1_00_00_000 });
    expect(screen.queryByRole('checkbox', { name: /from your wallet/i })).toBeInTheDocument();
  });

  it('switches the wallet on and pays the rest in cash', async () => {
    const calls = mockFetch((body) =>
      walletAwareQuote(25000, {
        wallet_applied_paise: (body as { use_wallet_paise?: number })?.use_wallet_paise ? 25000 : 0,
        total_paise: (body as { use_wallet_paise?: number })?.use_wallet_paise ? 35000 : 60000,
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<CheckoutPage />, { route: '/checkout' });

    const toggle = await screen.findByRole('checkbox', { name: /from your wallet/i });
    await user.click(toggle);

    await waitFor(() => {
      expect(screen.getByText('From your wallet')).toBeInTheDocument();
    });
    expect(screen.getByText('−₹250')).toBeInTheDocument();
    // The last quote asked for exactly the balance, not the probe maximum.
    const bodies = quoteBodies(calls) as { use_wallet_paise: number }[];
    expect(bodies.at(-1)?.use_wallet_paise).toBe(25000);
    expect(screen.getByRole('button', { name: /place order · ₹350/i })).toBeInTheDocument();
  });

  it('sends the wallet amount with the order and rotates the idempotency key', async () => {
    const calls = mockFetch((body) =>
      walletAwareQuote(25000, {
        wallet_applied_paise: (body as { use_wallet_paise?: number })?.use_wallet_paise ? 25000 : 0,
        total_paise: (body as { use_wallet_paise?: number })?.use_wallet_paise ? 35000 : 60000,
      }),
    );
    const user = userEvent.setup();
    renderWithProviders(<CheckoutPage />, { route: '/checkout' });

    const toggle = await screen.findByRole('checkbox', { name: /from your wallet/i });
    await user.click(toggle);
    const place = await screen.findByRole('button', { name: /place order/i });
    await waitFor(() => expect(place).toBeEnabled());
    await user.click(place);

    await waitFor(() => {
      const order = calls.find(
        (call) => call.url.endsWith('/api/v1/orders') && call.method === 'POST',
      );
      expect(order).toBeTruthy();
      expect(order?.body).toMatchObject({ use_wallet_paise: 25000 });
    });
  });

  it('hides the switch when the wallet is empty', async () => {
    mockFetch(() => walletAwareQuote(0));
    renderWithProviders(<CheckoutPage />, { route: '/checkout' });

    await screen.findByText('Order summary');
    await waitFor(() =>
      expect(screen.queryByRole('checkbox', { name: /from your wallet/i })).not.toBeInTheDocument(),
    );
  });
});
