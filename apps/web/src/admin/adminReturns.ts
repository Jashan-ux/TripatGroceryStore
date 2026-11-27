/**
 * Admin return queue data layer.
 *
 * Kept in the admin module graph: a customer's bundle never imports it. The only
 * mutating verbs are "decide" and "received" — money moves on the second one, in
 * the API, exactly once.
 */
import type { AdminReturnListOut, AdminReturnOut } from '@tripat/api-client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api } from '@/lib/api';

export type AdminReturnFilter = 'all' | 'requested' | 'approved' | 'rejected' | 'received_credited';

export const ADMIN_RETURNS_PAGE_SIZE = 20;

export function useAdminReturns({ status, page }: { status: AdminReturnFilter; page: number }) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(ADMIN_RETURNS_PAGE_SIZE),
  });
  if (status !== 'all') params.set('status', status);

  return useQuery<AdminReturnListOut>({
    queryKey: ['admin', 'returns', status, page],
    queryFn: ({ signal }) =>
      api.get<AdminReturnListOut>(`/api/v1/admin/returns?${params.toString()}`, { signal }),
    staleTime: 20 * 1000,
  });
}

function useReturnMutation<TArgs>(path: (returnId: string) => string) {
  const queryClient = useQueryClient();
  return useMutation<AdminReturnOut, Error, TArgs & { returnId: string }>({
    mutationFn: ({ returnId, ...body }) => api.post<AdminReturnOut>(path(returnId), body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'returns'] });
      // The customer's bell and wallet both changed.
      void queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
}

export function useDecideReturn() {
  return useReturnMutation<{ approve: boolean; note?: string }>(
    (id) => `/api/v1/admin/returns/${id}/decision`,
  );
}

export function useReceiveReturn() {
  return useReturnMutation<{ note?: string }>((id) => `/api/v1/admin/returns/${id}/received`);
}
