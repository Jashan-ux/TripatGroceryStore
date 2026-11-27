import { lazy, Suspense, type ReactNode } from 'react';
import { Link, Route, Routes } from 'react-router-dom';

import { AppShell } from '@/components/layout/AppShell';
import { Skeleton } from '@/components/ui/skeleton';
import { useCategories } from '@/features/catalogue/queries';
import { usePageTitle } from '@/hooks/usePageTitle';
import { t } from '@/i18n';
import CategoryPage from '@/pages/CategoryPage';
import ComingSoonPage from '@/pages/ComingSoonPage';
import ContactPage from '@/pages/ContactPage';
import HomePage from '@/pages/HomePage';
import NotFoundPage from '@/pages/NotFoundPage';
import ProductPage from '@/pages/ProductPage';
import SearchPage from '@/pages/SearchPage';
import { AdminGuard } from '@/routes/AdminGuard';
import { DeliveryGuard } from '@/routes/DeliveryGuard';
import { ProtectedRoute } from '@/routes/ProtectedRoute';

// Browsing (home, categories, search, product) ships in the first load; admin,
// account and auth screens are separate chunks. Auth pages carry the form and
// validation libraries, so keeping them out of the entry chunk is what keeps the
// initial budget honest.
const AdminRoutes = lazy(() => import('@/admin/AdminRoutes'));
const DeliveryPage = lazy(() =>
  import('@/delivery/DeliveryPage').then((module) => ({ default: module.DeliveryPage })),
);
const AuthCallbackPage = lazy(() => import('@/pages/auth/AuthCallbackPage'));
const ForgotPasswordPage = lazy(() => import('@/pages/auth/ForgotPasswordPage'));
const SignInPage = lazy(() => import('@/pages/auth/SignInPage'));
const SignUpPage = lazy(() => import('@/pages/auth/SignUpPage'));
const ProfilePage = lazy(() => import('@/pages/ProfilePage'));
// Cart and orders are their own chunks: browsing never pays for checkout.
const CartPage = lazy(() => import('@/pages/CartPage'));
const CheckoutPage = lazy(() => import('@/pages/CheckoutPage'));
const NotificationsPage = lazy(() => import('@/pages/NotificationsPage'));
const RewardsPage = lazy(() => import('@/pages/RewardsPage'));
const OrdersPage = lazy(() => import('@/pages/OrdersPage'));
const OrderDetailPage = lazy(() => import('@/pages/OrderDetailPage'));
/** One suspension boundary for every lazily-loaded route. */
function deferred(node: ReactNode) {
  return <Suspense fallback={<RouteFallback />}>{node}</Suspense>;
}

/** `/categories` is a real index of every department, not a placeholder. */
function CategoryIndexPage() {
  const { data, isPending } = useCategories();
  usePageTitle('nav.category');
  return (
    <div className="container py-6">
      <h1 className="mb-4 text-xl font-extrabold tracking-tight">All categories</h1>
      {isPending ? (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 6 }).map((_, index) => (
            <Skeleton key={index} className="h-24 w-full rounded-xl" />
          ))}
        </div>
      ) : (
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {(data ?? []).map((category) => (
            <li key={category.id} className="rounded-xl border border-border bg-card p-4">
              <Link
                to={`/categories/${category.slug}`}
                className="flex items-center gap-2 text-base font-bold hover:text-primary-700"
              >
                <span aria-hidden="true">{category.emoji ?? '🛒'}</span>
                {category.name}
              </Link>
              <ul className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-sm text-muted-foreground">
                {(category.children ?? []).map((child) => (
                  <li key={child.id}>
                    <Link to={`/categories/${child.slug}`} className="hover:text-primary-700">
                      {child.name}
                    </Link>
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

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
          <AdminGuard>
            <Suspense fallback={<RouteFallback />}>
              <AdminRoutes />
            </Suspense>
          </AdminGuard>
        }
      />
      <Route
        path="/delivery"
        element={<DeliveryGuard>{deferred(<DeliveryPage />)}</DeliveryGuard>}
      />
      <Route path="/auth/callback" element={deferred(<AuthCallbackPage />)} />
      <Route element={<AppShell />}>
        <Route index element={<HomePage />} />
        <Route path="search" element={<SearchPage />} />
        <Route path="categories" element={<CategoryIndexPage />} />
        <Route path="categories/:slug" element={<CategoryPage />} />
        <Route path="products/:slug" element={<ProductPage />} />
        <Route path="sign-in" element={deferred(<SignInPage />)} />
        <Route path="sign-up" element={deferred(<SignUpPage />)} />
        <Route path="forgot-password" element={deferred(<ForgotPasswordPage />)} />
        <Route path="cart" element={deferred(<CartPage />)} />
        <Route
          path="checkout"
          element={<ProtectedRoute>{deferred(<CheckoutPage />)}</ProtectedRoute>}
        />
        <Route
          path="orders"
          element={<ProtectedRoute>{deferred(<OrdersPage />)}</ProtectedRoute>}
        />
        <Route
          path="orders/:orderId"
          element={<ProtectedRoute>{deferred(<OrderDetailPage />)}</ProtectedRoute>}
        />
        <Route
          path="profile"
          element={<ProtectedRoute>{deferred(<ProfilePage />)}</ProtectedRoute>}
        />
        <Route
          path="notifications"
          element={<ProtectedRoute>{deferred(<NotificationsPage />)}</ProtectedRoute>}
        />
        <Route path="menu" element={<ComingSoonPage titleKey="nav.menu" />} />
        <Route
          path="rewards"
          element={<ProtectedRoute>{deferred(<RewardsPage />)}</ProtectedRoute>}
        />
        <Route path="contact" element={<ContactPage />} />
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
