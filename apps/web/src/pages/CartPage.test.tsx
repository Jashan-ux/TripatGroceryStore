import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import CartPage from '@/pages/CartPage';
import { CART_STORAGE_KEY } from '@/features/cart/storage';
import type { QuoteOut } from '@tripat/api-client';
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

const cart = {
  lines: [
    {
      productId: '11111111-1111-1111-1111-111111111111',
      variantId: null,
      slug: 'palak',
      name: 'Palak',
      unitLabel: '250 g',
      variantLabel: '',
      imageUrl: null,
      // Deliberately stale: the quote says ₹30, so the page must show ₹30.
      pricePaise: 2500,
      maxQuantity: 6,
      quantity: 2,
    },
    {
      productId: '22222222-2222-2222-2222-222222222222',
      variantId: '33333333-3333-3333-3333-333333333333',
      slug: 'aloo',
      name: 'Aloo',
      unitLabel: '1 kg',
      variantLabel: '1 kg pack',
      imageUrl: null,
      pricePaise: 4000,
      maxQuantity: 4,
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
        slug: 'palak',
        name: 'Palak',
        unit_label: '250 g',
        variant_label: '',
        image_url: '',
        quantity: 2,
        unit_price_paise: 3000,
        mrp_paise: 3500,
        line_total_paise: 6000,
        available_stock: 6,
        in_stock: true,
        issue: null,
      },
      {
        product_id: cart.lines[1]!.productId,
        variant_id: '33333333-3333-3333-3333-333333333333',
        slug: 'aloo',
        name: 'Aloo',
        unit_label: '1 kg',
        variant_label: '1 kg pack',
        image_url: '',
        quantity: 1,
        unit_price_paise: 4500,
        mrp_paise: 4500,
        line_total_paise: 4500,
        available_stock: 4,
        in_stock: true,
        issue: null,
      },
    ],
    subtotal_paise: 10500,
    delivery_fee_paise: 0,
    discount_paise: 0,
    discount_reason: '',
    wallet_available_paise: 0,
    wallet_applied_paise: 0,
    payable_before_wallet_paise: 10500,
    total_paise: 10500,
    item_count: 3,
    minimum_order_paise: 50000,
    shortfall_paise: 39500,
    deliver_by: '2026-11-26',
    delivery_days: 1,
    pincode: null,
    pincode_serviceable: null,
    blocking_issues: [
      {
        code: 'minimum_order',
        message: 'Add ₹395 more to reach the ₹500 minimum order.',
        details: {},
      },
    ],
    can_checkout: false,
    ...overrides,
  };
}

function mockFetch(payload: QuoteOut) {
  const calls: { url: string; body: unknown }[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    calls.push({ url, body: init?.body ? JSON.parse(String(init.body)) : null });
    const json = (body: unknown) =>
      new Response(JSON.stringify(body), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    if (url.includes('/api/v1/config')) return json(configResponse);
    if (url.includes('/api/v1/checkout/quote')) return json(payload);
    return new Response(JSON.stringify({ error: { code: 'not_found', message: 'no' } }), {
      status: 404,
    });
  });
  vi.stubGlobal('fetch', fetchMock);
  return calls;
}

describe('cart page', () => {
  beforeEach(() => {
    window.localStorage.setItem(CART_STORAGE_KEY, JSON.stringify(cart));
  });

  it('prices the basket from the server quote, not from the stored cart', async () => {
    mockFetch(quote());
    renderWithProviders(<CartPage />, { route: '/cart' });

    expect(screen.getByRole('heading', { name: 'Your cart' })).toBeInTheDocument();
    expect(screen.getByText('Palak')).toBeInTheDocument();
    expect(screen.getByText('Aloo')).toBeInTheDocument();

    // Quote unit price ₹30 (not the stale ₹25) and the quote's total.
    await waitFor(() => {
      expect(screen.getByText('₹30')).toBeInTheDocument();
    });
    // Item total and "To pay" both carry the server's ₹105 (not the stored ₹90).
    expect(screen.getAllByText('₹105').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('FREE')).toBeInTheDocument();
  });

  it('asks the API with ids and quantities only', async () => {
    const calls = mockFetch(quote());
    renderWithProviders(<CartPage />, { route: '/cart' });

    await waitFor(() => {
      const quoteCall = calls.find((call) => call.url.includes('/api/v1/checkout/quote'));
      expect(quoteCall).toBeTruthy();
      expect(quoteCall?.body).toEqual({
        items: [
          { product_id: cart.lines[0]!.productId, variant_id: null, quantity: 2 },
          {
            product_id: cart.lines[1]!.productId,
            variant_id: cart.lines[1]!.variantId,
            quantity: 1,
          },
        ],
        pincode: null,
        // The cart never spends the wallet; checkout is where that choice lives.
        use_wallet_paise: 0,
      });
    });
  });

  it('blocks checkout and explains why when the minimum order is not met', async () => {
    mockFetch(quote());
    renderWithProviders(<CartPage />, { route: '/cart' });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/minimum order/i);
    });
    expect(screen.getByRole('link', { name: 'Proceed to checkout' })).toHaveAttribute(
      'aria-disabled',
      'true',
    );
  });

  it('lets the shopper drop the count and remove a line', async () => {
    mockFetch(quote({ can_checkout: true, blocking_issues: [] }));
    renderWithProviders(<CartPage />, { route: '/cart' });

    const user = userEvent.setup();
    await screen.findByText('Palak');

    await user.click(screen.getByRole('button', { name: 'Remove one Palak' }));
    await waitFor(() => {
      expect(
        JSON.parse(window.localStorage.getItem(CART_STORAGE_KEY) ?? '{"lines":[]}').lines[0]
          .quantity,
      ).toBe(1);
    });

    await user.click(screen.getByRole('button', { name: 'Remove Aloo from cart' }));
    await waitFor(() => {
      expect(
        JSON.parse(window.localStorage.getItem(CART_STORAGE_KEY) ?? '{"lines":[]}').lines,
      ).toHaveLength(1);
    });
  });

  it('shows an empty state and keeps the cart clear of stale lines', () => {
    window.localStorage.removeItem(CART_STORAGE_KEY);
    mockFetch(quote());
    renderWithProviders(<CartPage />, { route: '/cart' });
    expect(screen.getByText('Your cart is empty')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Start shopping' })).toHaveAttribute(
      'href',
      '/categories',
    );
  });
});
