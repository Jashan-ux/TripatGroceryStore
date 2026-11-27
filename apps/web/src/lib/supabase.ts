/**
 * Supabase browser client.
 *
 * The URL and anon key are public values: in production they arrive from
 * `GET /api/v1/config` (which reads them from server-side settings), so a deploy
 * never has to rebuild the bundle to point at a different project. `VITE_*`
 * values act as a local-development override.
 *
 * The client is created lazily and memoised. Nothing else in the app is allowed
 * to construct one, and components never read tokens — `AuthProvider` wires the
 * only token seam (`setAccessTokenProvider`).
 */
import { createClient, type SupabaseClient } from '@supabase/supabase-js';

import { env } from './env';

export interface SupabaseConfig {
  url: string;
  anonKey: string;
}

let client: SupabaseClient | null = null;
let cachedConfig: SupabaseConfig | null = null;

export function resolveSupabaseConfig(fromServer?: Partial<SupabaseConfig>): SupabaseConfig {
  const url = env.supabaseUrl || fromServer?.url || '';
  const anonKey = env.supabaseAnonKey || fromServer?.anonKey || '';
  return { url, anonKey };
}

export function isAuthConfigured(config: SupabaseConfig): boolean {
  return Boolean(config.url && config.anonKey);
}

/** Create (or reuse) the singleton client. Throws only if auth is misconfigured. */
export function getSupabaseClient(config: SupabaseConfig): SupabaseClient {
  if (client && cachedConfig?.url === config.url) return client;
  if (!isAuthConfigured(config)) {
    throw new Error('Sign-in is not configured for this build.');
  }
  cachedConfig = config;
  client = createClient(config.url, config.anonKey, {
    auth: {
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
      // PKCE keeps the code verifier out of the URL fragment.
      flowType: 'pkce',
      storage: window.localStorage,
      storageKey: 'msg-store-auth',
    },
    global: { headers: { 'x-client-info': 'msg-store-web' } },
  });
  return client;
}

/** Test hook. */
export function resetSupabaseClient(): void {
  client = null;
  cachedConfig = null;
}
