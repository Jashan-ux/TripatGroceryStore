import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useEffect } from 'react';

import { OfflineBanner } from '@/components/common/OfflineBanner';
import { InstallPrompt } from '@/components/common/InstallPrompt';
import { UpdatePrompt } from '@/components/common/UpdatePrompt';
import { CartBar } from '@/components/cart/CartBar';
import { BottomNav } from '@/components/layout/BottomNav';
import { OfferBanner } from '@/components/layout/OfferBanner';
import { SiteFooter } from '@/components/layout/SiteFooter';
import { SiteHeader } from '@/components/layout/SiteHeader';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { PhonePrompt } from '@/features/auth/PhonePrompt';
import { useAuth } from '@/features/auth/useAuth';
import { CartProvider } from '@/features/cart/CartProvider';
import { StorePreviewProvider } from '@/features/store/StorePreviewContext';
import { useStoreConfig } from '@/hooks/useStoreConfig';
import { t } from '@/i18n';
import { cn } from '@/lib/utils';

const PREVIEW_KEY = 'msg-store-admin-preview';
const CUSTOMER_ONLY_PATHS = [
  '/cart',
  '/checkout',
  '/orders',
  '/profile',
  '/notifications',
  '/rewards',
  '/contact',
  '/sign-in',
  '/sign-up',
  '/forgot-password',
];

/** Storefront shell; customer basket UI is omitted in admin preview mode. */
export function AppShell() {
  const location = useLocation();
  const navigate = useNavigate();
  const { status, profile, isAdmin, error: profileError } = useAuth();
  const config = useStoreConfig();
  const previewInUrl = new URLSearchParams(location.search).get('preview') === '1';
  let persistedPreview = false;
  try {
    persistedPreview = window.sessionStorage.getItem(PREVIEW_KEY) === '1';
  } catch {
    // The URL flag can still start a one-page preview without browser storage.
  }
  const previewMode = isAdmin && (previewInUrl || persistedPreview);

  useEffect(() => {
    if (!isAdmin || !previewInUrl) return;
    try {
      window.sessionStorage.setItem(PREVIEW_KEY, '1');
    } catch {
      // The query flag still keeps this navigation in preview for this page.
    }
  }, [isAdmin, previewInUrl]);

  // Wait for the API-owned role before showing either experience; this prevents
  // a signed-in admin from seeing a flash of the customer storefront at startup.
  if (status === 'loading' || (status === 'authenticated' && !profile && !profileError)) {
    return (
      <div className="container space-y-3 py-8" role="status" aria-live="polite">
        <span className="sr-only">Checking your account</span>
        <Skeleton className="h-6 w-1/3" />
        <Skeleton className="h-32 w-full rounded-xl" />
      </div>
    );
  }
  if (status === 'authenticated' && !profile) {
    return (
      <div className="container max-w-lg py-10" role="alert">
        <p className="font-semibold">We could not load your account.</p>
        <p className="mt-1 text-sm text-muted-foreground">{profileError?.message}</p>
        <Button className="mt-3" onClick={() => window.location.reload()}>
          Try again
        </Button>
      </div>
    );
  }

  // Admins do not browse customer routes accidentally. The explicit preview is
  // session-scoped and read-only; account and transaction pages remain blocked.
  if (isAdmin && !previewMode) return <Navigate to="/admin" replace />;
  if (
    previewMode &&
    (CUSTOMER_ONLY_PATHS.includes(location.pathname) || location.pathname.startsWith('/orders/'))
  ) {
    return <Navigate to="/?preview=1" replace />;
  }

  const exitPreview = () => {
    try {
      window.sessionStorage.removeItem(PREVIEW_KEY);
    } catch {
      // Nothing else to clear when browser storage is unavailable.
    }
    void navigate('/admin', { replace: true });
  };

  return (
    <StorePreviewProvider value={previewMode}>
      <CartProvider>
        <div className="flex min-h-dvh flex-col">
          {previewMode && (
            <div className="sticky top-0 z-50 flex min-h-11 items-center justify-center gap-3 bg-amber-100 px-3 text-sm font-semibold text-amber-950">
              <span>Preview mode</span>
              <Button size="sm" variant="outline" onClick={exitPreview}>
                Exit
              </Button>
            </div>
          )}
          {!previewMode && config.data?.store_open === false && (
            <div className="bg-destructive px-3 py-2 text-center text-sm font-semibold text-destructive-foreground">
              Store closed — ordering is temporarily unavailable.
            </div>
          )}
          <a
            href="#main"
            className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
          >
            {t('nav.skipToContent')}
          </a>
          <UpdatePrompt />
          <OfflineBanner />
          <InstallPrompt />
          <SiteHeader />
          <OfferBanner />
          <main id="main" tabIndex={-1} className={cn('flex-1 outline-none')}>
            <div key={location.pathname} className="animate-none">
              <Outlet />
            </div>
          </main>
          <SiteFooter />
          {!previewMode && <CartBar />}
          {!previewMode && <BottomNav />}
          {!previewMode && <PhonePrompt />}
        </div>
      </CartProvider>
    </StorePreviewProvider>
  );
}
