import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, type RenderOptions } from '@testing-library/react';
import type { ReactElement, ReactNode } from 'react';
import { MemoryRouter } from 'react-router-dom';

import { AuthProvider } from '@/features/auth/AuthProvider';
import { CartProvider } from '@/features/cart/CartProvider';

/**
 * Test renderer: fresh QueryClient per test (no cache bleed), a router, the real
 * AuthProvider and the real CartProvider — the same wrapper stack the app shell
 * gives every page. Auth resolves to "anonymous" whenever the mocked
 * `/api/v1/config` returns empty Supabase keys, which is the default fixture.
 * Cart tests seed `localStorage` before rendering.
 */
export function renderWithProviders(
  ui: ReactElement,
  { route = '/', ...options }: RenderOptions & { route?: string } = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[route]}>
          <AuthProvider>
            <CartProvider>{children}</CartProvider>
          </AuthProvider>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }

  return { queryClient, ...render(ui, { wrapper: Wrapper, ...options }) };
}
