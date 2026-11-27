/**
 * Auth state for the whole app.
 *
 * One provider owns the Supabase session and pushes the access token into the
 * single API seam (`setAccessTokenProvider`). Components read `useAuth()` and
 * never touch tokens or the Supabase client directly, so swapping providers or
 * adding MFA later is a change in this file only.
 *
 * Roles are *not* read from the session: the API resolves the role from
 * `profiles.role`, and the client only mirrors what the API says.
 */
import type { ProfileOut } from '@tripat/api-client';
import type { Session } from '@supabase/supabase-js';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';

import { useStoreConfig } from '@/hooks/useStoreConfig';
import { api, setAccessTokenProvider, setUnauthorizedHandler, type ApiError } from '@/lib/api';
import { authRedirectUrl, safeInternalPath } from '@/lib/navigation';
import { getSupabaseClient, isAuthConfigured, resolveSupabaseConfig } from '@/lib/supabase';

import { AuthContext, PROFILE_QUERY_KEY, type AuthContextValue, type AuthStatus } from './context';

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const configQuery = useStoreConfig();
  // `undefined` = not read yet, `null` = signed out. Status is derived from this
  // rather than stored, so an effect never has to write state synchronously.
  const [session, setSession] = useState<Session | null | undefined>(undefined);

  const supabaseConfig = useMemo(
    () =>
      resolveSupabaseConfig(
        configQuery.data
          ? {
              url: configQuery.data.supabase_url ?? '',
              anonKey: configQuery.data.supabase_anon_key ?? '',
            }
          : undefined,
      ),
    [configQuery.data],
  );

  const authAvailable = isAuthConfigured(supabaseConfig);
  const client = useMemo(
    () => (authAvailable ? getSupabaseClient(supabaseConfig) : null),
    [authAvailable, supabaseConfig],
  );

  // The token seam: every API request asks here; nothing else reads the session.
  useEffect(() => {
    setAccessTokenProvider(async () => {
      if (!client) return null;
      const { data } = await client.auth.getSession();
      return data.session?.access_token ?? null;
    });
    setUnauthorizedHandler(async () => {
      if (client) await client.auth.signOut({ scope: 'local' });
    });
    return () => {
      setAccessTokenProvider(() => null);
      setUnauthorizedHandler(null);
    };
  }, [client]);

  useEffect(() => {
    if (!client) return;
    let active = true;
    let authEventReceived = false;
    void client.auth
      .getSession()
      .then(({ data }) => {
        if (active && !authEventReceived) setSession(data.session);
      })
      .catch(() => {
        // Resolve the startup gate even if browser storage/session recovery fails.
        if (active && !authEventReceived) setSession(null);
      });
    const { data: subscription } = client.auth.onAuthStateChange((event, nextSession) => {
      if (!active) return;
      authEventReceived = true;
      setSession(nextSession);
      if (event === 'SIGNED_OUT') {
        queryClient.clear();
      }
    });
    return () => {
      active = false;
      subscription.subscription.unsubscribe();
    };
  }, [client, queryClient]);

  const status: AuthStatus = !authAvailable
    ? configQuery.isPending
      ? 'loading'
      : 'anonymous'
    : session === undefined
      ? 'loading'
      : session
        ? 'authenticated'
        : 'anonymous';

  const profileQuery = useQuery<ProfileOut, ApiError>({
    queryKey: [...PROFILE_QUERY_KEY, session?.user.id],
    queryFn: ({ signal }) => api.get<ProfileOut>('/api/v1/me', { signal }),
    enabled: Boolean(session) && status === 'authenticated',
    staleTime: 30_000,
    retry: (count, error) => error.status >= 500 && count < 2,
  });

  const refreshProfile = useCallback(async () => {
    await queryClient.invalidateQueries({ queryKey: PROFILE_QUERY_KEY });
  }, [queryClient]);

  const requireClient = useCallback(() => {
    if (!client) throw new Error('Sign-in is not configured for this build.');
    return client;
  }, [client]);

  const signInWithPassword = useCallback(
    async (email: string, password: string) => {
      const { error } = await requireClient().auth.signInWithPassword({ email, password });
      if (error) throw error;
    },
    [requireClient],
  );

  const signUpWithPassword = useCallback(
    async (email: string, password: string, name: string) => {
      const { data, error } = await requireClient().auth.signUp({
        email,
        password,
        options: {
          data: { full_name: name },
          emailRedirectTo: authRedirectUrl('/auth/callback'),
        },
      });
      if (error) throw error;
      // With email confirmation on, Supabase returns a user but no session.
      return { needsEmailConfirmation: !data.session };
    },
    [requireClient],
  );

  const signInWithGoogle = useCallback(
    async (next = '/') => {
      const safeNext = safeInternalPath(next, '/');
      const redirectTo = `${authRedirectUrl('/auth/callback')}?next=${encodeURIComponent(safeNext)}`;
      const { error } = await requireClient().auth.signInWithOAuth({
        provider: 'google',
        options: { redirectTo, queryParams: { prompt: 'select_account' } },
      });
      if (error) throw error;
    },
    [requireClient],
  );

  const sendPasswordReset = useCallback(
    async (email: string) => {
      const { error } = await requireClient().auth.resetPasswordForEmail(email, {
        redirectTo: `${authRedirectUrl('/auth/callback')}?next=/reset-password`,
      });
      if (error) throw error;
    },
    [requireClient],
  );

  const signOut = useCallback(async () => {
    if (!client) return;
    await client.auth.signOut();
    queryClient.clear();
  }, [client, queryClient]);

  const value = useMemo<AuthContextValue>(
    () => ({
      status,
      session: session ?? null,
      user: session?.user ?? null,
      profile: profileQuery.data ?? null,
      isAdmin: profileQuery.data?.role === 'admin',
      authAvailable,
      needsPhone: Boolean(profileQuery.data && !profileQuery.data.has_phone),
      error: profileQuery.error ?? null,
      refreshProfile,
      signInWithPassword,
      signUpWithPassword,
      signInWithGoogle,
      sendPasswordReset,
      signOut,
    }),
    [
      status,
      session,
      profileQuery.data,
      profileQuery.error,
      authAvailable,
      refreshProfile,
      signInWithPassword,
      signUpWithPassword,
      signInWithGoogle,
      sendPasswordReset,
      signOut,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
