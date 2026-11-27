import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/useAuth';

/** Client navigation gate only; every admin API independently enforces AdminUserDep. */
export function AdminGuard({ children }: { children: ReactNode }) {
  const { status, profile, isAdmin, error, refreshProfile } = useAuth();

  if (status === 'loading' || (status === 'authenticated' && !profile && !error)) {
    return (
      <div className="container space-y-3 py-8" role="status" aria-live="polite">
        <span className="sr-only">Checking merchant access</span>
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-32 w-full rounded-xl" />
      </div>
    );
  }

  if (status === 'anonymous') {
    return <Navigate to="/sign-in?next=%2Fadmin" replace />;
  }

  if (error && !profile) {
    return (
      <div className="container max-w-lg py-10" role="alert">
        <h1 className="text-lg font-bold">We could not verify merchant access</h1>
        <p className="mt-1 text-sm text-muted-foreground">{error.message}</p>
        <Button className="mt-3" onClick={() => void refreshProfile()}>
          Try again
        </Button>
      </div>
    );
  }

  if (!isAdmin) return <Navigate to="/" replace />;
  return <>{children}</>;
}
