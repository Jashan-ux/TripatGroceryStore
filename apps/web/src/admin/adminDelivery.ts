import type {
  DeliveryCandidateOut,
  DeliveryProfileOut,
  AdminOrderSummaryOut,
} from '@tripat/api-client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api';

export function useDeliveryProfiles() {
  return useQuery<DeliveryProfileOut[]>({
    queryKey: ['admin', 'delivery', 'profiles'],
    queryFn: ({ signal }) =>
      api.get<DeliveryProfileOut[]>('/api/v1/admin/delivery/profiles', { signal }),
  });
}

export function useDeliveryCandidates(query: string) {
  const params = new URLSearchParams();
  if (query.trim()) params.set('q', query.trim());
  return useQuery<DeliveryCandidateOut[]>({
    queryKey: ['admin', 'delivery', 'candidates', query],
    queryFn: ({ signal }) =>
      api.get<DeliveryCandidateOut[]>(`/api/v1/admin/delivery/candidates?${params}`, { signal }),
  });
}

export function usePromoteDeliveryProfile() {
  const queryClient = useQueryClient();
  return useMutation<DeliveryProfileOut, Error, string>({
    mutationFn: (profileId) =>
      api.post<DeliveryProfileOut>('/api/v1/admin/delivery/profiles', { profile_id: profileId }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'delivery'] });
    },
  });
}

export function useAssignDefaultOrder(orderId: string) {
  const queryClient = useQueryClient();
  return useMutation<AdminOrderSummaryOut, Error, void>({
    mutationFn: () =>
      api.post<AdminOrderSummaryOut>(`/api/v1/admin/orders/${orderId}/assign-default`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'orders'] });
      void queryClient.invalidateQueries({ queryKey: ['admin', 'order'] });
    },
  });
}

export function useAssignOrder(orderId: string) {
  const queryClient = useQueryClient();
  return useMutation<AdminOrderSummaryOut, Error, string | null>({
    mutationFn: (profileId) =>
      api.patch<AdminOrderSummaryOut>(`/api/v1/admin/orders/${orderId}/assignment`, {
        profile_id: profileId,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'orders'] });
      void queryClient.invalidateQueries({ queryKey: ['admin', 'order'] });
    },
  });
}
