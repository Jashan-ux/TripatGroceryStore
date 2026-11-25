import { AdminActivityPage } from '@/admin/AdminActivityPage';
import { AdminBrandsPage } from '@/admin/AdminBrandsPage';
import { AdminCategoriesPage } from '@/admin/AdminCategoriesPage';
import { AdminFeedbackPage } from '@/admin/AdminFeedbackPage';
import { AdminLayout } from '@/admin/AdminLayout';
import { AdminOffersPage } from '@/admin/AdminOffersPage';
import { AdminOrdersPage } from '@/admin/AdminOrdersPage';
import { AdminProductsPage } from '@/admin/AdminProductsPage';
import { AdminReturnsPage } from '@/admin/AdminReturnsPage';
import { AdminSectionPage } from '@/admin/AdminSectionPage';
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
        <Route
          index
          element={
            <AdminSectionPage
              titleKey="admin.analytics"
              summary="Sales, products and customers in one place. No outside analytics needed."
              bullets={[
                'Revenue, average order value, repeat rate and pending cash-on-delivery totals.',
                'Daily trend plus breakdowns by category, brand, status and pincode.',
                'Every card drills down to the orders behind the number.',
              ]}
            />
          }
        />
        <Route path="orders" element={<AdminOrdersPage />} />
        <Route path="returns" element={<AdminReturnsPage />} />
        <Route path="products" element={<AdminProductsPage />} />
        <Route path="brands" element={<AdminBrandsPage />} />
        <Route
          path="customers"
          element={
            <AdminSectionPage
              titleKey="admin.customers"
              summary="Who shops with you, and how much trust they have placed in the store."
              bullets={[
                'Lifetime spend and loyalty badge for every customer.',
                'Tier filters and search by name, phone or email.',
                'A profile view lists every past order.',
              ]}
            />
          }
        />
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
