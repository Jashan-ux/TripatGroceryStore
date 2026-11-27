import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import RewardsPage from '@/pages/RewardsPage';

// Behind `ProtectedRoute` in the app: hand the page a signed-in session directly.
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

const summary = {
  wallet: {
    balance_paise: 12500,
    total: 2,
    page: 1,
    page_size: 20,
    total_pages: 1,
    entries: [
      {
        id: 'eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee',
        delta_paise: 10000,
        reason: 'referral_bonus',
        note: 'Aman joined with your code',
        order_id: null,
        created_at: '2026-11-24T10:00:00Z',
      },
      {
        id: 'ffffffff-ffff-ffff-ffff-ffffffffffff',
        delta_paise: 2500,
        reason: 'scratch_card',
        note: '',
        order_id: null,
        created_at: '2026-11-23T10:00:00Z',
      },
    ],
  },
  referrals: {
    code: 'JASHAN42',
    share_url: '/join?ref=JASHAN42',
    friend_discount_pct: 10,
    referrer_reward_paise: 2000,
    joined: 1,
    credited: 1,
    earned_paise: 2000,
    friends: [
      {
        name: 'Aman',
        status: 'credited',
        reward_paise: 2000,
        joined_at: '2026-11-20T10:00:00Z',
        credited_at: '2026-11-22T10:00:00Z',
      },
    ],
    my_referral: null,
  },
  scratch: {
    cards: [
      {
        id: 'c1c1c1c1-c1c1-c1c1-c1c1-c1c1c1c1c1c1',
        status: 'ready',
        threshold_paise: 200000,
        amount_paise: null,
        order_id: '22222222-2222-2222-2222-222222222222',
        order_number: 'MSG-261124-AAAAA',
        unlocked_at: '2026-11-24T10:00:00Z',
        expires_at: '2026-12-24T10:00:00Z',
        revealed_at: null,
        created_at: '2026-11-24T09:00:00Z',
      },
      {
        id: 'c2c2c2c2-c2c2-c2c2-c2c2-c2c2c2c2c2c2',
        status: 'locked',
        threshold_paise: 200000,
        amount_paise: null,
        order_id: '33333333-3333-3333-3333-333333333333',
        order_number: 'MSG-261125-BBBBB',
        unlocked_at: null,
        expires_at: null,
        revealed_at: null,
        created_at: '2026-11-25T09:00:00Z',
      },
    ],
    ready: 1,
    locked: 1,
    revealed: 0,
  },
  tier: {
    tier: 'gold',
    spend_paise: 2500000,
    next_tier: 'platinum',
    next_tier_at_paise: 5000000,
    remaining_paise: 2500000,
    progress_pct: 50,
  },
};

function mockFetch(overrides: { reveal?: unknown; join?: unknown } = {}) {
  const calls: { url: string; method: string; body: unknown }[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      const method = init?.method ?? 'GET';
      calls.push({ url, method, body: init?.body ? JSON.parse(String(init.body)) : null });
      const json = (body: unknown, status = 200) =>
        new Response(JSON.stringify(body), {
          status,
          headers: { 'Content-Type': 'application/json' },
        });

      if (url.includes('/api/v1/config')) return json(configResponse);
      if (url.includes('/reveal')) {
        return json(
          overrides.reveal ?? {
            card: { ...summary.scratch.cards[0], status: 'revealed', amount_paise: 7500 },
            credited_paise: 7500,
            wallet_balance_paise: 20000,
          },
        );
      }
      if (url.includes('/api/v1/rewards/referral') && method === 'POST') {
        return json(overrides.join ?? { ...summary.referrals, my_referral: null }, 200);
      }
      if (url.includes('/api/v1/rewards/scratch-cards')) return json(summary.scratch);
      if (url.includes('/api/v1/rewards/wallet')) return json(summary.wallet);
      if (url.includes('/api/v1/rewards')) return json(summary);
      return json({ error: { code: 'not_found', message: 'no' } }, 404);
    }),
  );
  return calls;
}

describe('RewardsPage', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    // jsdom's navigator has no writable clipboard, so define it outright.
    Object.defineProperty(navigator, 'clipboard', {
      configurable: true,
      value: { writeText: vi.fn(async () => undefined) },
    });
  });

  it('shows the wallet balance and where the money came from', async () => {
    mockFetch();
    renderWithProviders(<RewardsPage />, { route: '/rewards' });

    expect(await screen.findByText('₹125')).toBeInTheDocument();
    expect(screen.getByText('Referral reward')).toBeInTheDocument();
    expect(screen.getByText('+₹100')).toBeInTheDocument();
    expect(screen.getByText('Scratch card')).toBeInTheDocument();
    expect(screen.getByText('+₹25')).toBeInTheDocument();
  });

  it('offers the referral code and the friend list', async () => {
    mockFetch();
    renderWithProviders(<RewardsPage />, { route: '/rewards' });

    expect(await screen.findByText('JASHAN42')).toBeInTheDocument();
    expect(screen.getByText(/10% off their first order/)).toBeInTheDocument();
    // The wallet note mentions the friend too, so the list is one of several.
    expect(screen.getAllByText(/Aman/).length).toBeGreaterThan(1);
    expect(screen.getByRole('button', { name: /copy link/i })).toBeInTheDocument();
  });

  it('scrubs a ready card and shows the amount the server chose', async () => {
    const calls = mockFetch();
    renderWithProviders(<RewardsPage />, { route: '/rewards' });

    const cards = await screen.findByRole('region', { name: 'Scratch cards' });
    expect(within(cards).getByText('Ready to scratch')).toBeInTheDocument();
    expect(within(cards).getByText('Locked until delivery')).toBeInTheDocument();

    await userEvent.setup().click(within(cards).getByRole('button', { name: /scratch/i }));

    await waitFor(() => {
      expect(calls.some((call) => call.url.endsWith('/reveal') && call.method === 'POST')).toBe(
        true,
      );
    });
  });

  it('shows the badge and how far the next one is', async () => {
    mockFetch();
    renderWithProviders(<RewardsPage />, { route: '/rewards' });

    expect(await screen.findByText('Gold member')).toBeInTheDocument();
    const bar = screen.getByRole('progressbar', { name: /next badge/i });
    expect(bar).toHaveAttribute('aria-valuenow', '50');
    expect(screen.getByText(/₹25,000 more for Platinum member/)).toBeInTheDocument();
  });

  it('sends a friend code in upper case and clears the box on success', async () => {
    const calls = mockFetch({
      join: {
        ...summary.referrals,
        my_referral: {
          code: 'AMAN99',
          status: 'pending',
          discount_paise: 0,
          referrer_name: 'Aman',
        },
      },
    });
    const user = userEvent.setup();
    renderWithProviders(<RewardsPage />, { route: '/rewards' });

    await user.type(await screen.findByLabelText(/friend's code/i), 'aman99');
    await user.click(screen.getByRole('button', { name: /use code/i }));

    await waitFor(() => {
      const call = calls.find((entry) => entry.url.includes('/api/v1/rewards/referral'));
      expect(call?.method).toBe('POST');
      expect(call?.body).toEqual({ code: 'AMAN99' });
    });
  });
});
