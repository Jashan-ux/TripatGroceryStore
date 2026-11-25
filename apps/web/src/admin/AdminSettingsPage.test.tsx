import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AdminSettingsPage } from '@/admin/AdminSettingsPage';
import { renderWithProviders } from '@/test/render';

const settings = {
  store_name: 'Tripat Pansari MSG Store',
  store_phone: '+91 87089-73386',
  store_address: 'near Sabji Mandi, Mandi Dabwali, 125104',
  store_maps_url: 'https://maps.app.goo.gl/example',
  feedback_email: 'store@example.com',
  notification_email: 'owner@example.com',
  minimum_order_paise: 50000,
  serviceable_pincodes: ['125104'],
  default_delivery_days: 1,
  low_stock_threshold: 5,
  referral_referrer_reward_paise: 10000,
  referral_friend_discount_pct: 10,
  scratch_threshold_paise: 100000,
  scratch_min_paise: 1000,
  scratch_max_paise: 5000,
  scratch_expiry_days: 30,
  return_window_days: 2,
  tier_gold_paise: 500000,
  tier_platinum_paise: 1000000,
  tier_diamond_paise: 2500000,
  updated_at: '2026-11-01T10:00:00Z',
};

interface Call {
  url: string;
  method: string;
  body: unknown;
}

function mockFetch(options: { reject?: boolean } = {}) {
  const calls: Call[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? 'GET';
      const body = typeof init?.body === 'string' ? JSON.parse(init.body) : null;
      calls.push({ url, method, body });
      const json = (payload: unknown, status = 200) =>
        new Response(JSON.stringify(payload), {
          status,
          headers: { 'Content-Type': 'application/json' },
        });

      if (url.includes('/api/v1/config')) {
        return json({
          environment: 'test',
          store_name: settings.store_name,
          store_phone: settings.store_phone,
          store_address: settings.store_address,
          store_maps_url: settings.store_maps_url,
          feedback_email: settings.feedback_email,
          phone_otp_enabled: false,
          turnstile_enabled: false,
          supabase_url: '',
          supabase_anon_key: '',
          vapid_public_key: '',
        });
      }
      if (url.includes('/api/v1/admin/settings')) {
        if (method === 'PATCH') {
          if (options.reject) {
            return json(
              {
                error: {
                  code: 'invalid_settings',
                  message: 'Gold cannot be above Platinum.',
                  details: {},
                },
              },
              422,
            );
          }
          return json({ ...settings, ...(body as object), updated_at: '2026-11-25T10:00:00Z' });
        }
        return json(settings);
      }
      return json({ error: { code: 'not_found', message: 'no' } }, 404);
    }),
  );
  return calls;
}

describe('AdminSettingsPage', () => {
  beforeEach(() => vi.unstubAllGlobals());

  it('shows the money the shop runs on, in rupees', async () => {
    mockFetch();
    renderWithProviders(<AdminSettingsPage />, { route: '/admin/settings' });

    const minimum = await screen.findByLabelText(/minimum order \(₹\)/i);
    expect(minimum).toHaveValue('500.00');
    expect(screen.getByLabelText(/gold tier at \(₹\)/i)).toHaveValue('5000.00');
  });

  it('saves rupees back to the API as paise and says it applies immediately', async () => {
    const calls = mockFetch();
    const user = userEvent.setup();
    renderWithProviders(<AdminSettingsPage />, { route: '/admin/settings' });

    const minimum = await screen.findByLabelText(/minimum order \(₹\)/i);
    await user.clear(minimum);
    await user.type(minimum, '750');
    await user.click(screen.getByRole('button', { name: /save settings/i }));

    await waitFor(() => {
      const patch = calls.find((call) => call.method === 'PATCH');
      expect(patch?.body).toMatchObject({ minimum_order_paise: 75000 });
    });
    expect(await screen.findByText(/the next checkout already uses these numbers/i)).toBeVisible();
  });

  it('shows the server’s refusal instead of pretending it saved', async () => {
    mockFetch({ reject: true });
    const user = userEvent.setup();
    renderWithProviders(<AdminSettingsPage />, { route: '/admin/settings' });

    await user.click(await screen.findByRole('button', { name: /save settings/i }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Gold cannot be above Platinum.');
    expect(screen.queryByText(/the next checkout already uses/i)).not.toBeInTheDocument();
  });

  it('sends pincodes as a clean list', async () => {
    const calls = mockFetch();
    const user = userEvent.setup();
    renderWithProviders(<AdminSettingsPage />, { route: '/admin/settings' });

    const pincodes = await screen.findByLabelText(/serviceable pincodes/i);
    await user.clear(pincodes);
    await user.type(pincodes, '125104, 125105');
    await user.click(screen.getByRole('button', { name: /save settings/i }));

    await waitFor(() => {
      const patch = calls.find((call) => call.method === 'PATCH');
      expect(patch?.body).toMatchObject({ serviceable_pincodes: ['125104', '125105'] });
    });
  });
});
