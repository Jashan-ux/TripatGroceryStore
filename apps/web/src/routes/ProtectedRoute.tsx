import type { ReactNode } from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/useAuth';

/**
 * Client-side gate. It only decides *what to render* — authorisation itself is
 * enforced by the API on every request, so bypassing this component grants
 * nothing beyond a friendly redirect.
 */
export function ProtectedRoute({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === 'loading') {
    return (
      <div className="container space-y-3 py-8" role="status" aria-live="polite">
        <span className="sr-only">Checking your session</span>
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-32 w-full rounded-xl" />
      </div>
    );
  }

  if (status === 'anonymous') {
    const next = `${location.pathname}${location.search}`;
    return <Navigate to={`/sign-in?next=${encodeURIComponent(next)}`} replace />;
  }

  return <>{children}</>;
}
