/**
 * Build-time configuration. Anything secret belongs on the server. Supabase's
 * URL and publishable key are explicitly public and may be supplied through the
 * NEXT_PUBLIC_* names, with the existing VITE_* names retained as fallbacks.
 */
export type ImportMetaEnvLike = Record<string, string | boolean | undefined>;

const rawEnv = (import.meta as unknown as { env: ImportMetaEnvLike }).env ?? {};

function readString(source: ImportMetaEnvLike, key: string): string {
  const value = source[key];
  return typeof value === 'string' ? value.trim() : '';
}

export function resolveSupabaseBuildConfig(source: ImportMetaEnvLike = rawEnv) {
  return {
    supabaseUrl:
      readString(source, 'NEXT_PUBLIC_SUPABASE_URL') || readString(source, 'VITE_SUPABASE_URL'),
    supabaseAnonKey:
      readString(source, 'NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY') ||
      readString(source, 'VITE_SUPABASE_ANON_KEY'),
  };
}

export function resolveApiBaseUrl(source: ImportMetaEnvLike = rawEnv): string {
  return readString(source, 'VITE_API_BASE_URL').replace(/\/$/, '');
}

const supabaseBuildConfig = resolveSupabaseBuildConfig();

export const env = {
  /** Empty string means same-origin: the browser calls /api/* and Vercel rewrites. */
  apiBaseUrl: resolveApiBaseUrl(),
  mode: readString(rawEnv, 'VITE_APP_MODE') || 'production',
  /** Set only for local development; production normally reads these from /api/v1/config. */
  supabaseUrl: supabaseBuildConfig.supabaseUrl,
  supabaseAnonKey: supabaseBuildConfig.supabaseAnonKey,
} as const;

export const isDev = rawEnv.DEV === true || rawEnv.DEV === 'true';
