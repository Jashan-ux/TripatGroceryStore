import { useEffect, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/useAuth';
import { usePageTitle } from '@/hooks/usePageTitle';
import { safeInternalPath } from '@/lib/navigation';

/**
 * Landing page for email-confirmation and OAuth redirects.
 *
 * Supabase parses the session out of the URL (`detectSessionInUrl`), so this page
 * only waits for the provider to resolve, then forwards to `?next=`. If nothing
 * resolves (expired link, cancelled consent) it offers a way forward instead of
 * spinning forever.
 */
export default function AuthCallbackPage() {
  usePageTitle('auth.signInTitle');
  const { status, profile } = useAuth();
  const [params] = useSearchParams();
  const [timedOut, setTimedOut] = useState(false);
  const next = safeInternalPath(params.get('next'));

  useEffect(() => {
    if (status === 'authenticated' && profile) {
      window.location.replace(profile.role === 'admin' ? '/admin' : next);
      return;
    }
    const timer = window.setTimeout(() => setTimedOut(true), 8000);
    return () => window.clearTimeout(timer);
  }, [status, profile, next]);

  return (
    <div className="container max-w-md space-y-3 py-12" role="status" aria-live="polite">
      {timedOut && !(status === 'authenticated' && profile) ? (
        <>
          <h1 className="text-xl font-bold">That link did not work</h1>
          <p className="text-sm text-muted-foreground">
            The confirmation link may have expired. Sign in again, or create a new account.
          </p>
          <div className="flex gap-2">
            <Button asChild>
              <Link to="/sign-in">Sign in</Link>
            </Button>
            <Button asChild variant="outline">
              <Link to="/sign-up">Create account</Link>
            </Button>
          </div>
        </>
      ) : (
        <>
          <span className="sr-only">Finishing sign-in</span>
          <Skeleton className="h-6 w-1/2" />
          <Skeleton className="h-24 w-full rounded-xl" />
        </>
      )}
    </div>
  );
}
