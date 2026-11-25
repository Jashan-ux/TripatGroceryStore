/**
 * Build-time configuration. Anything secret belongs on the server — this file
 * may only ever read `VITE_*` values that are safe to ship in a bundle.
 */
type ImportMetaEnvLike = Record<string, string | boolean | undefined>;

const rawEnv = (import.meta as unknown as { env: ImportMetaEnvLike }).env ?? {};

function readString(key: string, fallback = ''): string {
  const value = rawEnv[key];
  return typeof value === 'string' && value.length > 0 ? value : fallback;
}

export const env = {
  /** Empty string means same-origin: the browser calls /api/* and Vercel rewrites. */
  apiBaseUrl: readString('VITE_API_BASE_URL').replace(/\/$/, ''),
  mode: readString('VITE_APP_MODE', 'production'),
  /** Set only for local development against a Supabase project; prod reads it from /api/v1/config. */
  supabaseUrl: readString('VITE_SUPABASE_URL'),
  supabaseAnonKey: readString('VITE_SUPABASE_ANON_KEY'),
} as const;

export const isDev = rawEnv.DEV === true || rawEnv.DEV === 'true';
