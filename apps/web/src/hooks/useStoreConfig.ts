import { useQuery } from '@tanstack/react-query';
import type { PublicConfig } from '@tripat/api-client';

import { api } from '@/lib/api';

/**
 * Store contact and runtime flags come from the server (store_settings), never
 * from hard-coded constants in components.
 */
export function useStoreConfig() {
  return useQuery<PublicConfig>({
    queryKey: ['config'],
    queryFn: ({ signal }) => api.get<PublicConfig>('/api/v1/config', { signal }),
    staleTime: 60 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
  });
}
