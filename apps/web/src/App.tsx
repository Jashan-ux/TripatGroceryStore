import { lazy, Suspense } from 'react';
import { Route, Routes } from 'react-router-dom';

import { AppShell } from '@/components/layout/AppShell';
import { Skeleton } from '@/components/ui/skeleton';
import { t } from '@/i18n';
import ComingSoonPage from '@/pages/ComingSoonPage';
import HomePage from '@/pages/HomePage';
import NotFoundPage from '@/pages/NotFoundPage';
import SearchPage from '@/pages/SearchPage';

// Admin code is a separate chunk: `React.lazy` + a dynamic import means the
// customer bundle never contains admin modules.
const AdminRoutes = lazy(() => import('@/admin/AdminRoutes'));

function RouteFallback() {
  return (
    <div className="container space-y-4 py-8" role="status" aria-live="polite">
      <span className="sr-only">{t('common.loading')}</span>
      <Skeleton className="h-8 w-1/2" />
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-40 w-full rounded-xl" />
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route
        path="/admin/*"
        element={
          <Suspense fallback={<RouteFallback />}>
            <AdminRoutes />
          </Suspense>
        }
      />
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="categories" element={<ComingSoonPage titleKey="nav.category" />} />
        <Route path="cart" element={<ComingSoonPage titleKey="nav.cart" />} />
        <Route path="orders" element={<ComingSoonPage titleKey="nav.orders" />} />
        <Route path="profile" element={<ComingSoonPage titleKey="nav.profile" />} />
        <Route path="notifications" element={<ComingSoonPage titleKey="nav.notifications" />} />
        <Route path="menu" element={<ComingSoonPage titleKey="nav.menu" />} />
        <Route path="rewards" element={<ComingSoonPage titleKey="footer.rewards" />} />
        <Route path="contact" element={<ComingSoonPage titleKey="footer.contactUs" />} />
        <Route path="policies/privacy" element={<ComingSoonPage titleKey="footer.privacy" />} />
        <Route path="policies/terms" element={<ComingSoonPage titleKey="footer.terms" />} />
        <Route
          path="policies/shipping"
          element={<ComingSoonPage titleKey="footer.shippingInfo" />}
        />
        <Route path="policies/returns" element={<ComingSoonPage titleKey="footer.returns" />} />
        <Route path="policies/faq" element={<ComingSoonPage titleKey="footer.faq" />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
