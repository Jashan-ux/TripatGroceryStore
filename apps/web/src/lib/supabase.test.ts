import { afterEach, describe, expect, it, vi } from 'vitest';

const { createClientMock } = vi.hoisted(() => ({ createClientMock: vi.fn() }));

vi.mock('@supabase/supabase-js', () => ({ createClient: createClientMock }));

import { getSupabaseClient, resetSupabaseClient } from './supabase';

afterEach(() => {
  resetSupabaseClient();
  createClientMock.mockReset();
});

describe('Supabase browser session persistence', () => {
  it('persists and refreshes auth through explicit browser localStorage', () => {
    createClientMock.mockReturnValue({ auth: {} });

    getSupabaseClient({ url: 'https://project.supabase.co', anonKey: 'public-key' });

    const options = createClientMock.mock.calls[0]?.[2] as {
      auth: Record<string, unknown>;
    };
    expect(options.auth).toMatchObject({
      persistSession: true,
      autoRefreshToken: true,
      detectSessionInUrl: true,
      flowType: 'pkce',
      storageKey: 'msg-store-auth',
      storage: window.localStorage,
    });
  });
});
