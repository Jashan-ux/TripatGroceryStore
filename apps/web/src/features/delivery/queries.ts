import type { DeliveryOrderListOut, DeliveryOrderOut } from '@tripat/api-client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api';

export const DELIVERY_ORDERS_KEY = ['delivery', 'orders'] as const;

export function useDeliveryOrders() {
  return useQuery<DeliveryOrderListOut>({
    queryKey: DELIVERY_ORDERS_KEY,
    queryFn: ({ signal }) => api.get<DeliveryOrderListOut>('/api/v1/delivery/orders', { signal }),
    refetchInterval: 30_000,
  });
}

export function useDeliveryAction() {
  const queryClient = useQueryClient();
  return useMutation<
    DeliveryOrderOut,
    Error,
    { orderId: string; action: 'out-for-delivery' | 'delivered' }
  >({
    mutationFn: ({ orderId, action }) =>
      api.post<DeliveryOrderOut>(`/api/v1/delivery/orders/${orderId}/${action}`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: DELIVERY_ORDERS_KEY }),
  });
}
