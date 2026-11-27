/**
 * The owner's numbers (Phase 6).
 *
 * One cache key shape — `['admin','analytics', kind, range]` — so changing the
 * date chips refetches exactly the screens that depend on the range and nothing
 * else. The summary and its drill-down share the range key on purpose: when the
 * card and the list below it were fetched for the same range they cannot disagree
 * on screen, which is the failure the acceptance criteria care about.
 */
import type {
  AnalyticsOrderListOut,
  AnalyticsSummaryOut,
  CustomerListOut,
  CustomerProfileOut,
  LowStockListOut,
  ProductSalesListOut,
  SeriesOut,
} from '@tripat/api-client';
import { useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api';

export interface RangeParams {
  from: string;
  to: string;
}

function rangeQuery(range: RangeParams): string {
  return `from_date=${range.from}&to_date=${range.to}`;
}

export function useAnalyticsSummary(range: RangeParams) {
  return useQuery<AnalyticsSummaryOut>({
    queryKey: ['admin', 'analytics', 'summary', range],
    queryFn: ({ signal }) =>
      api.get<AnalyticsSummaryOut>(`/api/v1/admin/analytics/summary?${rangeQuery(range)}`, {
        signal,
      }),
  });
}

export function useAnalyticsSeries(range: RangeParams) {
  return useQuery<SeriesOut>({
    queryKey: ['admin', 'analytics', 'series', range],
    queryFn: ({ signal }) =>
      api.get<SeriesOut>(`/api/v1/admin/analytics/series?${rangeQuery(range)}`, { signal }),
  });
}

export function useAnalyticsOrders(range: RangeParams, enabled = true) {
  return useQuery<AnalyticsOrderListOut>({
    queryKey: ['admin', 'analytics', 'orders', range],
    queryFn: ({ signal }) =>
      api.get<AnalyticsOrderListOut>(
        `/api/v1/admin/analytics/orders?${rangeQuery(range)}&page_size=25`,
        { signal },
      ),
    enabled,
  });
}

export function useTopProducts(range: RangeParams) {
  return useQuery<ProductSalesListOut>({
    queryKey: ['admin', 'analytics', 'products', range],
    queryFn: ({ signal }) =>
      api.get<ProductSalesListOut>(`/api/v1/admin/analytics/products?${rangeQuery(range)}`, {
        signal,
      }),
  });
}

export function useLowStock() {
  return useQuery<LowStockListOut>({
    queryKey: ['admin', 'analytics', 'low-stock'],
    queryFn: ({ signal }) =>
      api.get<LowStockListOut>('/api/v1/admin/analytics/low-stock', { signal }),
  });
}

export function useAdminCustomers(params: { q: string; tier: string; sort: string; page: number }) {
  const search = new URLSearchParams({
    sort: params.sort,
    page: String(params.page),
    page_size: '20',
  });
  if (params.q.trim()) search.set('q', params.q.trim());
  if (params.tier) search.set('tier', params.tier);
  return useQuery<CustomerListOut>({
    queryKey: ['admin', 'customers', params],
    queryFn: ({ signal }) =>
      api.get<CustomerListOut>(`/api/v1/admin/customers?${search.toString()}`, { signal }),
  });
}

export function useCustomerProfile(customerId: string | null) {
  return useQuery<CustomerProfileOut>({
    queryKey: ['admin', 'customer', customerId],
    queryFn: ({ signal }) =>
      api.get<CustomerProfileOut>(`/api/v1/admin/customers/${customerId}`, { signal }),
    enabled: Boolean(customerId),
  });
}
