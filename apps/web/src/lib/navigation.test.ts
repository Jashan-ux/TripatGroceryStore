import { describe, expect, it } from 'vitest';

import {
  authRedirectUrl,
  CANONICAL_SITE_ORIGIN,
  publicSiteUrl,
  safeInternalPath,
} from './navigation';

describe('auth redirect and internal navigation URLs', () => {
  it('uses the configured canonical site for preview and production hosts', () => {
    expect(authRedirectUrl('/auth/callback', 'https://branch-preview.vercel.app')).toBe(
      `${CANONICAL_SITE_ORIGIN}/auth/callback`,
    );
    expect(authRedirectUrl('/auth/callback', 'https://tripatmsg.in')).toBe(
      `${CANONICAL_SITE_ORIGIN}/auth/callback`,
    );
  });

  it('pins share links to the canonical host and rejects external paths', () => {
    expect(publicSiteUrl('/rewards?ref=ABC', 'https://branch-preview.vercel.app')).toBe(
      `${CANONICAL_SITE_ORIGIN}/rewards?ref=ABC`,
    );
    expect(publicSiteUrl('//evil.example/path', 'https://tripatmsg.in')).toBe(
      `${CANONICAL_SITE_ORIGIN}/`,
    );
  });

  it('keeps local authentication callbacks on the local dev origin', () => {
    expect(authRedirectUrl('/auth/callback', 'http://localhost:5173')).toBe(
      'http://localhost:5173/auth/callback',
    );
  });

  it('preserves safe in-app destinations and rejects off-site redirects', () => {
    expect(safeInternalPath('/orders?tab=active#latest')).toBe('/orders?tab=active#latest');
    expect(safeInternalPath('https://evil.example/steal')).toBe('/profile');
    expect(safeInternalPath('//evil.example/steal')).toBe('/profile');
    expect(safeInternalPath('/\\\\evil.example')).toBe('/profile');
  });
});
