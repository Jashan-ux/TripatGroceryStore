import {
  BarChart3,
  Boxes,
  LayoutGrid,
  Megaphone,
  ReceiptText,
  Settings,
  Users,
} from 'lucide-react';

/** Top tab strip (tablet/desktop) and bottom nav (mobile) share this list. */
export const adminSections = [
  { to: '/admin', labelKey: 'admin.analytics', icon: BarChart3, end: true, mobile: true },
  { to: '/admin/orders', labelKey: 'admin.orders', icon: ReceiptText, end: false, mobile: true },
  { to: '/admin/products', labelKey: 'admin.products', icon: Boxes, end: false, mobile: true },
  { to: '/admin/customers', labelKey: 'admin.customers', icon: Users, end: false, mobile: true },
  {
    to: '/admin/categories',
    labelKey: 'admin.categories',
    icon: LayoutGrid,
    end: false,
    mobile: false,
  },
  { to: '/admin/offers', labelKey: 'admin.offers', icon: Megaphone, end: false, mobile: false },
  { to: '/admin/settings', labelKey: 'admin.settings', icon: Settings, end: false, mobile: true },
] as const;
