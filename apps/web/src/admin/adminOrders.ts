/**
 * Admin order data layer.
 *
 * Lives in the admin module graph on purpose: nothing here is imported by a
 * customer route, so the owner's tooling stays out of the customer bundle.
 */
import type {
  AdminOrderListOut,
  AdminOrderStatusIn,
  AdminOrderSummaryOut,
  OrderOut,
} from '@tripat/api-client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api';

export type AdminStatusFilter =
  | 'all'
  | 'processing'
  | 'accepted'
  | 'packing'
  | 'shipped'
  | 'out_for_delivery'
  | 'delivered'
  | 'cancelled';

export const ADMIN_PAGE_SIZE = 20;

export function adminOrdersKey(
  status: AdminStatusFilter,
  q: string,
  page: number,
  date: string,
  payment: string,
) {
  return ['admin', 'orders', status, q, date, payment, page] as const;
}

export function useAdminOrders({
  status,
  q,
  date,
  payment,
  page,
}: {
  status: AdminStatusFilter;
  q: string;
  date: string;
  payment: string;
  page: number;
}) {
  const params = new URLSearchParams({ page: String(page), page_size: String(ADMIN_PAGE_SIZE) });
  if (status !== 'all') params.set('status', status);
  if (q.trim()) params.set('q', q.trim());
  if (date) params.set('date', date);
  if (payment) params.set('payment_status', payment);

  return useQuery<AdminOrderListOut>({
    queryKey: adminOrdersKey(status, q, page, date, payment),
    queryFn: ({ signal }) =>
      api.get<AdminOrderListOut>(`/api/v1/admin/orders?${params.toString()}`, { signal }),
    // The counter phone wants fresh numbers, but not a refetch storm.
    staleTime: 20 * 1000,
  });
}

export function useAdminOrder(orderId: string | null) {
  return useQuery<OrderOut>({
    queryKey: ['admin', 'order', orderId],
    queryFn: ({ signal }) => api.get<OrderOut>(`/api/v1/admin/orders/${orderId}`, { signal }),
    enabled: Boolean(orderId),
  });
}

export function useSetOrderStatus() {
  const queryClient = useQueryClient();
  return useMutation<
    AdminOrderSummaryOut,
    Error,
    { orderId: string; status: AdminOrderStatusIn['status']; note?: string }
  >({
    mutationFn: ({ orderId, status, note }) =>
      api.post<AdminOrderSummaryOut>(`/api/v1/admin/orders/${orderId}/status`, {
        status,
        note: note ?? '',
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'orders'] });
      void queryClient.invalidateQueries({ queryKey: ['admin', 'order'] });
    },
  });
}

export function useSetOrderDeliveryDays() {
  const queryClient = useQueryClient();
  return useMutation<AdminOrderSummaryOut, Error, { orderId: string; days: number; note?: string }>(
    {
      mutationFn: ({ orderId, days, note }) =>
        api.patch<AdminOrderSummaryOut>(`/api/v1/admin/orders/${orderId}/delivery-days`, {
          days,
          note: note ?? '',
        }),
      onSuccess: () => {
        void queryClient.invalidateQueries({ queryKey: ['admin', 'orders'] });
        void queryClient.invalidateQueries({ queryKey: ['admin', 'order'] });
        // The customer's bell gains a line, so their count is stale too.
        void queryClient.invalidateQueries({ queryKey: ['notifications'] });
      },
    },
  );
}

/** The single next step the shop should take, if any. */
export function nextStep(
  status: string,
): { status: AdminOrderStatusIn['status']; label: string } | null {
  switch (status) {
    case 'processing':
      return { status: 'accepted', label: 'Accept order' };
    case 'accepted':
      return { status: 'packing', label: 'Start packing' };
    case 'packing':
      return { status: 'shipped', label: 'Mark packed & ready' };
    case 'shipped':
      return { status: 'out_for_delivery', label: 'Out for delivery' };
    case 'out_for_delivery':
      return { status: 'delivered', label: 'Mark delivered' };
    default:
      return null;
  }
}
