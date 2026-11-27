/** Canonical public origin. Vercel sends the apex domain to its www domain. */
export const CANONICAL_SITE_ORIGIN = 'https://www.tripatmsg.in';

function isLocalDevelopmentOrigin(origin: string): boolean {
  try {
    const hostname = new URL(origin).hostname;
    return hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '[::1]';
  } catch {
    return false;
  }
}

/**
 * Keep local development convenient, but never derive public links from the
 * active production or preview host (which may be a Vercel alias).
 */
export function publicSiteUrl(path: string, currentOrigin = window.location.origin): string {
  const origin = isLocalDevelopmentOrigin(currentOrigin) ? currentOrigin : CANONICAL_SITE_ORIGIN;
  const safePath = safeInternalPath(path, '/');
  return new URL(safePath, origin).toString();
}

export function authRedirectUrl(path: string, currentOrigin = window.location.origin): string {
  return publicSiteUrl(path, currentOrigin);
}

/** Accept only same-origin app paths, rejecting protocol-relative and absolute URLs. */
export function safeInternalPath(value: string | null | undefined, fallback = '/profile'): string {
  if (!value || !value.startsWith('/') || value.startsWith('//') || value.includes('\\')) {
    return fallback;
  }
  try {
    const parsed = new URL(value, CANONICAL_SITE_ORIGIN);
    if (parsed.origin !== CANONICAL_SITE_ORIGIN || parsed.username || parsed.password)
      return fallback;
    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return fallback;
  }
}
