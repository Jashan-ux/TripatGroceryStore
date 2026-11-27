import { describe, expect, it } from 'vitest';

import { resolveSupabaseBuildConfig } from './env';

describe('resolveSupabaseBuildConfig', () => {
  it('prefers the explicit NEXT_PUBLIC Supabase variables', () => {
    expect(
      resolveSupabaseBuildConfig({
        NEXT_PUBLIC_SUPABASE_URL: ' https://project.supabase.co ',
        NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: 'publishable-key',
        VITE_SUPABASE_URL: 'https://legacy.supabase.co',
        VITE_SUPABASE_ANON_KEY: 'legacy-key',
      }),
    ).toEqual({
      supabaseUrl: 'https://project.supabase.co',
      supabaseAnonKey: 'publishable-key',
    });
  });

  it('supports the existing VITE_* variables as a fallback', () => {
    expect(
      resolveSupabaseBuildConfig({
        VITE_SUPABASE_URL: 'https://legacy.supabase.co',
        VITE_SUPABASE_ANON_KEY: 'legacy-key',
      }),
    ).toEqual({
      supabaseUrl: 'https://legacy.supabase.co',
      supabaseAnonKey: 'legacy-key',
    });
  });

  it('treats empty preferred variables as unset', () => {
    expect(
      resolveSupabaseBuildConfig({
        NEXT_PUBLIC_SUPABASE_URL: '  ',
        NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY: '',
        VITE_SUPABASE_URL: 'https://legacy.supabase.co',
        VITE_SUPABASE_ANON_KEY: 'legacy-key',
      }),
    ).toEqual({
      supabaseUrl: 'https://legacy.supabase.co',
      supabaseAnonKey: 'legacy-key',
    });
  });
});
