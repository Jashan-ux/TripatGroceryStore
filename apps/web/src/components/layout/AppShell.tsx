import { lazy, Suspense, useState } from 'react';
import { Navigate, Outlet, useLocation } from 'react-router-dom';

import { OfflineBanner } from '@/components/common/OfflineBanner';
import { InstallPrompt } from '@/components/common/InstallPrompt';
import { UpdatePrompt } from '@/components/common/UpdatePrompt';
import { CartBar } from '@/components/cart/CartBar';
import { BottomNav } from '@/components/layout/BottomNav';
import { OfferBanner } from '@/components/layout/OfferBanner';
import { SiteFooter } from '@/components/layout/SiteFooter';
import { SiteHeader } from '@/components/layout/SiteHeader';
import { PhonePrompt } from '@/features/auth/PhonePrompt';
import { useAuth } from '@/features/auth/useAuth';
import { CartProvider } from '@/features/cart/CartProvider';
import { AdminStoreViewProvider } from '@/features/store/StorePreviewContext';
import { StorefrontAdminProvider } from '@/features/store/StorefrontAdminContext';
import { useStoreConfig } from '@/hooks/useStoreConfig';
import { t } from '@/i18n';
import { cn } from '@/lib/utils';

const StorefrontAdminBar = lazy(() =>
  import('@/admin/StorefrontAdminBar').then((module) => ({ default: module.StorefrontAdminBar })),
);
const StorefrontProductEditor = lazy(() =>
  import('@/admin/StorefrontProductEditor').then((module) => ({
    default: module.StorefrontProductEditor,
  })),
);

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

/** Customer storefront shell with admin-only editing tools layered onto it. */
export function AppShell() {
  const location = useLocation();
  const { profile, isAdmin } = useAuth();
  const config = useStoreConfig();
  const [editingProductId, setEditingProductId] = useState<string | null>(null);
  const [adminNotice, setAdminNotice] = useState<string | null>(null);
  // Admins work in the same storefront page customers see, with editing tools
  // layered over it; there is no separate read-only preview mode.
  const adminStoreMode = isAdmin;
  // Public storefront routes render even while identity/configuration is still
  // loading or the device is offline. No admin tools are shown until the API
  // confirms the role; the separate /admin route remains gated independently.

  // Delivery profiles use their own route surface; admins keep the storefront
  // as their workspace and receive the editing toolbar there.
  if (profile?.role === 'delivery') return <Navigate to="/delivery" replace />;
  if (
    adminStoreMode &&
    (CUSTOMER_ONLY_PATHS.includes(location.pathname) || location.pathname.startsWith('/orders/'))
  ) {
    return <Navigate to="/" replace />;
  }

  return (
    <AdminStoreViewProvider value={adminStoreMode}>
      <StorefrontAdminProvider
        value={
          adminStoreMode ? { editProduct: (productId) => setEditingProductId(productId) } : null
        }
      >
        <CartProvider>
          <div className={cn('flex min-h-dvh flex-col', adminStoreMode && 'pb-nav-safe')}>
            {adminStoreMode && (
              <Suspense fallback={null}>
                <>
                  <StorefrontAdminBar />
                  {adminNotice && (
                    <div className="container max-w-screen-2xl pt-2">
                      <p
                        role="status"
                        className="rounded-md bg-success-soft px-3 py-1.5 text-sm text-success"
                      >
                        {adminNotice}
                      </p>
                    </div>
                  )}
                </>
              </Suspense>
            )}
            {!adminStoreMode && config.data?.store_open === false && (
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
            {!adminStoreMode && <CartBar />}
            <BottomNav />
            {!adminStoreMode && <PhonePrompt />}
          </div>
          {adminStoreMode && editingProductId && (
            <Suspense fallback={null}>
              <StorefrontProductEditor
                open
                productId={editingProductId}
                onClose={() => setEditingProductId(null)}
                onSaved={setAdminNotice}
              />
            </Suspense>
          )}
        </CartProvider>
      </StorefrontAdminProvider>
    </AdminStoreViewProvider>
  );
}
