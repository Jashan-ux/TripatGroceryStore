import { QueryClient } from '@tanstack/react-query';

import { ApiError } from './api';

/**
 * Sensible defaults for a mid/low-end Android on 4G: retry transient failures
 * only, never retry a 4xx (it will fail the same way and wastes data), and keep
 * data fresh for a short window so navigation back is instant.
 */
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 10 * 60_000,
      refetchOnWindowFocus: false,
      retry: (failureCount, error) => {
        if (error instanceof ApiError) {
          if (error.status >= 400 && error.status < 500) return false;
        }
        return failureCount < 2;
      },
      retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, 8000),
    },
    mutations: { retry: false },
  },
});
