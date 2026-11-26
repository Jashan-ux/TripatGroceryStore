import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { AdminAnalyticsPage } from '@/admin/AdminAnalyticsPage';
import { AdminCustomersPage } from '@/admin/AdminCustomersPage';
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

const fromDate = '2026-11-01';
const toDate = '2026-11-30';

function mockFetch() {
  const calls: string[] = [];
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      calls.push(url);
      const json = (payload: unknown) =>
        new Response(JSON.stringify(payload), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      if (url.includes('/api/v1/config')) return json(configResponse);
      if (url.includes('/api/v1/admin/analytics/summary')) {
        return json({
          range: { from_date: fromDate, to_date: toDate, days: 30, timezone: 'Asia/Kolkata' },
          revenue_paise: 125000,
          orders: 2,
          average_order_paise: 62500,
          items_sold: 4,
          new_customers: 1,
          repeat_customers: 1,
          repeat_rate_percent: 50,
          cash_pending_paise: 50000,
          by_status: { processing: 1, delivered: 1 },
          low_stock: 1,
        });
      }
      if (url.includes('/api/v1/admin/analytics/series')) {
        return json({
          range: { from_date: fromDate, to_date: toDate, days: 30, timezone: 'Asia/Kolkata' },
          points: [
            { day: fromDate, orders: 0, revenue_paise: 0 },
            { day: toDate, orders: 2, revenue_paise: 125000 },
          ],
        });
      }
      if (url.includes('/api/v1/admin/analytics/orders')) {
        return json({
          items: [
            {
              id: '11111111-1111-1111-1111-111111111111',
              order_number: 'MSG-261125-ABCDE',
              status: 'processing',
              total_paise: 125000,
              item_count: 4,
              placed_at: '2026-11-25T08:30:00Z',
              customer_name: 'Rani',
              customer_phone: '9876543210',
              customer_id: '22222222-2222-2222-2222-222222222222',
            },
          ],
          page: 1,
          page_size: 25,
          total: 2,
          total_pages: 1,
          total_paise: 125000,
        });
      }
      if (url.includes('/api/v1/admin/analytics/products')) {
        return json({
          range: { from_date: fromDate, to_date: toDate, days: 30, timezone: 'Asia/Kolkata' },
          items: [],
          total_revenue_paise: 0,
          total_units: 0,
        });
      }
      if (url.includes('/api/v1/admin/analytics/low-stock')) {
        return json({ items: [], total: 0 });
      }
      if (url.includes('/api/v1/admin/customers')) {
        return json({
          items: [
            {
              id: '22222222-2222-2222-2222-222222222222',
              name: 'Rani Sharma',
              phone: '+919876543210',
              email: 'rani@example.com',
              tier: 'gold',
              lifetime_spend_paise: 250000,
              orders: 4,
              last_order_at: '2026-11-25T08:30:00Z',
              is_top: true,
            },
          ],
          page: 1,
          page_size: 20,
          total: 1,
          total_pages: 1,
          counts: { bronze: 8, silver: 3, gold: 1, platinum: 0 },
        });
      }
      return json({ error: { code: 'not_found', message: 'No test response for this URL.' } });
    }),
  );
  return calls;
}

describe('Phase 6 admin screens', () => {
  beforeEach(() => vi.unstubAllGlobals());

  it('opens the orders behind the revenue card for the exact same date range', async () => {
    const calls = mockFetch();
    const user = userEvent.setup();
    renderWithProviders(<AdminAnalyticsPage />, { route: '/admin' });

    expect(await screen.findByText('Daily takings')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Revenue/ }));
    expect(await screen.findByText(/The orders behind/)).toBeInTheDocument();
    expect(await screen.findByText('MSG-261125-ABCDE')).toBeInTheDocument();
    const summary = calls.find((url) => url.includes('/analytics/summary'));
    const orders = calls.find((url) => url.includes('/analytics/orders'));
    expect(summary).toBeDefined();
    expect(orders).toBeDefined();
    const summaryRange = new URLSearchParams(summary?.split('?')[1]);
    const orderRange = new URLSearchParams(orders?.split('?')[1]);
    expect(orderRange.get('from_date')).toBe(summaryRange.get('from_date'));
    expect(orderRange.get('to_date')).toBe(summaryRange.get('to_date'));
  });

  it('shows customer tiers and sends the selected tier filter to the API', async () => {
    const calls = mockFetch();
    const user = userEvent.setup();
    renderWithProviders(<AdminCustomersPage />, { route: '/admin/customers' });

    expect(await screen.findByText('Rani Sharma')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Gold 1/ })).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Gold/ }));
    await waitFor(() => {
      expect(
        calls.some((url) => url.includes('/api/v1/admin/customers?') && url.includes('tier=gold')),
      ).toBe(true);
    });
    expect(screen.getByRole('link', { name: /Rani Sharma/ })).toHaveAttribute(
      'href',
      '/admin/customers/22222222-2222-2222-2222-222222222222',
    );
  });
});
