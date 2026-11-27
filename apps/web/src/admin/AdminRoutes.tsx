import { AdminActivityPage } from '@/admin/AdminActivityPage';
import { AdminBrandsPage } from '@/admin/AdminBrandsPage';
import { AdminCategoriesPage } from '@/admin/AdminCategoriesPage';
import { AdminAnalyticsPage } from '@/admin/AdminAnalyticsPage';
import { AdminCustomerProfilePage } from '@/admin/AdminCustomerProfilePage';
import { AdminCustomersPage } from '@/admin/AdminCustomersPage';
import { AdminFeedbackPage } from '@/admin/AdminFeedbackPage';
import { AdminLayout } from '@/admin/AdminLayout';
import { AdminInventoryPage } from '@/admin/AdminInventoryPage';
import { AdminOffersPage } from '@/admin/AdminOffersPage';
import { AdminOrdersPage } from '@/admin/AdminOrdersPage';
import { AdminProductsPage } from '@/admin/AdminProductsPage';
import { AdminReturnsPage } from '@/admin/AdminReturnsPage';
import { AdminSettingsPage } from '@/admin/AdminSettingsPage';
import NotFoundPage from '@/pages/NotFoundPage';
import { Route, Routes } from 'react-router-dom';

/**
 * Entry point of the lazily-loaded admin bundle. Nothing in this module graph is
 * imported by customer code, so Recharts and the admin tooling never reach a
 * customer's phone.
 */
export default function AdminRoutes() {
  return (
    <Routes>
      <Route element={<AdminLayout />}>
        <Route index element={<AdminAnalyticsPage />} />
        <Route path="orders" element={<AdminOrdersPage />} />
        <Route path="returns" element={<AdminReturnsPage />} />
        <Route path="products" element={<AdminProductsPage />} />
        <Route path="inventory" element={<AdminInventoryPage />} />
        <Route path="brands" element={<AdminBrandsPage />} />
        <Route path="customers" element={<AdminCustomersPage />} />
        <Route path="customers/:customerId" element={<AdminCustomerProfilePage />} />
        <Route path="categories" element={<AdminCategoriesPage />} />
        <Route path="offers" element={<AdminOffersPage />} />
        <Route path="settings" element={<AdminSettingsPage />} />
        <Route path="feedback" element={<AdminFeedbackPage />} />
        <Route path="activity" element={<AdminActivityPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
