import { AdminLayout } from '@/admin/AdminLayout';
import { AdminOrdersPage } from '@/admin/AdminOrdersPage';
import { AdminReturnsPage } from '@/admin/AdminReturnsPage';
import { AdminSectionPage } from '@/admin/AdminSectionPage';
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
        <Route
          path="products"
          element={
            <AdminSectionPage
              titleKey="admin.products"
              summary="Manage your store inventory."
              bullets={[
                'Inline add on any category row, plus a spreadsheet-style bulk add with a dry-run preview.',
                'Edit prices, stock, units and variants from a dialog sized for a phone.',
                'Image uploads are validated, re-encoded and stored in Supabase Storage.',
              ]}
            />
          }
        />
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
        <Route
          path="categories"
          element={
            <AdminSectionPage
              titleKey="admin.categories"
              summary="Each category becomes a row in the catalog. Add subcategories for finer groups."
              bullets={[
                'Create, edit, reorder and nest categories.',
                'Emoji or an uploaded image — never emoji-only.',
                'Deleting a category that still has products is blocked or reassigns them.',
              ]}
            />
          }
        />
        <Route
          path="offers"
          element={
            <AdminSectionPage
              titleKey="admin.offers"
              summary="Every customer sees this in the notification bell of their app."
              bullets={[
                'Send to everyone or to a single loyalty tier.',
                'In-app bell, slide-down banner and web push.',
                'Full history of what was sent and when.',
              ]}
            />
          }
        />
        <Route
          path="settings"
          element={
            <AdminSectionPage
              titleKey="admin.settings"
              summary="Delivery area, minimum order and rewards."
              bullets={[
                'Minimum order, serviceable pincodes and default delivery days.',
                'Referral, scratch-card, return-window and loyalty values.',
                'Every change is audit-logged and applies on the next checkout.',
              ]}
            />
          }
        />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
