import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, render, screen, waitFor } from '@testing-library/react';
import type { Session } from '@supabase/supabase-js';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const { getSessionMock, onAuthStateChangeMock, signOutMock, apiGetMock } = vi.hoisted(() => ({
  getSessionMock: vi.fn(),
  onAuthStateChangeMock: vi.fn(),
  signOutMock: vi.fn(),
  apiGetMock: vi.fn(),
}));

vi.mock('@/hooks/useStoreConfig', () => ({
  useStoreConfig: () => ({
    data: { supabase_url: 'https://project.supabase.co', supabase_anon_key: 'public-key' },
    isPending: false,
  }),
}));

vi.mock('@/lib/api', () => ({
  api: { get: apiGetMock },
  setAccessTokenProvider: vi.fn(),
  setUnauthorizedHandler: vi.fn(),
}));

vi.mock('@/lib/supabase', () => ({
  resolveSupabaseConfig: (server?: { url?: string; anonKey?: string }) => ({
    url: server?.url ?? '',
    anonKey: server?.anonKey ?? '',
  }),
  isAuthConfigured: (config: { url: string; anonKey: string }) =>
    Boolean(config.url && config.anonKey),
  getSupabaseClient: () => ({
    auth: {
      getSession: getSessionMock,
      onAuthStateChange: onAuthStateChangeMock,
      signOut: signOutMock,
    },
  }),
}));

import { AuthProvider } from './AuthProvider';
import { ProtectedRoute } from '@/routes/ProtectedRoute';

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

function renderProtectedPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={['/profile']}>
          <Routes>
            <Route
              path="/profile"
              element={
                <ProtectedRoute>
                  <p>Protected profile content</p>
                </ProtectedRoute>
              }
            />
            <Route path="/sign-in" element={<p>Sign-in screen</p>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
});

describe('AuthProvider session hydration', () => {
  it('holds protected navigation until the persisted Supabase session is restored', async () => {
    const sessionRead = deferred<{ data: { session: Session | null } }>();
    const session = { access_token: 'restored-token', user: { id: 'user-1' } } as Session;
    getSessionMock.mockReturnValue(sessionRead.promise);
    onAuthStateChangeMock.mockReturnValue({
      data: { subscription: { unsubscribe: vi.fn() } },
    });
    apiGetMock.mockResolvedValue({ role: 'customer' });

    renderProtectedPage();

    expect(screen.getByText('Checking your session')).toBeInTheDocument();
    expect(screen.queryByText('Sign-in screen')).not.toBeInTheDocument();
    expect(screen.queryByText('Protected profile content')).not.toBeInTheDocument();

    await act(async () => {
      sessionRead.resolve({ data: { session } });
      await sessionRead.promise;
    });

    await waitFor(() => expect(screen.getByText('Protected profile content')).toBeInTheDocument());
    expect(screen.queryByText('Sign-in screen')).not.toBeInTheDocument();
  });
});
