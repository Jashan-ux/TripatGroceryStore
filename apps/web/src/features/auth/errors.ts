/**
 * Translate provider errors into copy a shopkeeper's customer can act on.
 *
 * Supabase returns English strings with status codes; matching on the message
 * (case-insensitively, by substring) is the only stable contract it offers for
 * the auth endpoints used here. Anything unknown falls back to a neutral
 * message plus the support phone, which is always better than a raw error.
 */
export function authErrorMessage(error: unknown, fallback: string): string {
  const message =
    typeof error === 'string'
      ? error
      : error && typeof error === 'object' && 'message' in error
        ? String(error.message)
        : '';
  const text = message.toLowerCase();

  if (text.includes('invalid login credentials')) return 'That email and password do not match.';
  if (text.includes('email not confirmed'))
    return 'Please confirm your email address — check your inbox for the link.';
  if (text.includes('user already registered'))
    return 'This email is already registered. Please sign in.';
  if (text.includes('password should be at least'))
    return 'Choose a password of at least 8 characters.';
  if (text.includes('rate limit') || text.includes('too many'))
    return 'Too many attempts. Please wait a minute and try again.';
  if (text.includes('provider is not enabled'))
    return 'Google sign-in is not enabled yet. Please use your email and password.';
  if (text.includes('network') || text.includes('failed to fetch'))
    return 'We could not reach the sign-in service. Check your connection.';
  if (text.includes('signups not allowed'))
    return 'New sign-ups are paused. Please call the store.';
  return fallback;
}
