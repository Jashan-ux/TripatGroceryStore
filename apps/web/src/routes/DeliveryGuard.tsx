import type { ReactNode } from 'react';
import { Navigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/useAuth';

export function DeliveryGuard({ children }: { children: ReactNode }) {
  const { status, profile, error, refreshProfile } = useAuth();

  if (status === 'loading' || (status === 'authenticated' && !profile && !error)) {
    return (
      <main className="mx-auto min-h-dvh w-full max-w-lg space-y-3 p-4" role="status">
        <span className="sr-only">Checking delivery access</span>
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-28 w-full rounded-xl" />
      </main>
    );
  }
  if (status === 'anonymous') return <Navigate to="/sign-in?next=%2Fdelivery" replace />;
  if (!profile && error) {
    return (
      <main className="mx-auto max-w-lg p-4" role="alert">
        <h1 className="font-bold">We could not verify delivery access.</h1>
        <p className="mt-1 text-sm text-muted-foreground">{error.message}</p>
        <Button className="mt-3" onClick={() => void refreshProfile()}>
          Try again
        </Button>
      </main>
    );
  }
  if (profile?.role !== 'delivery') {
    return <Navigate to={profile?.role === 'admin' ? '/admin' : '/'} replace />;
  }
  return <>{children}</>;
}
