import { Home, LayoutGrid, ReceiptText, ShoppingBag, User } from 'lucide-react';
import { NavLink } from 'react-router-dom';

import { useStorePreview } from '@/features/store/StorePreviewContext';
import { useCart } from '@/features/cart/useCart';
import { t } from '@/i18n';
import { cn } from '@/lib/utils';

const items = [
  { to: '/', labelKey: 'nav.home', icon: Home, end: true },
  { to: '/categories', labelKey: 'nav.category', icon: LayoutGrid, end: false },
  { to: '/cart', labelKey: 'nav.cart', icon: ShoppingBag, end: false },
  { to: '/orders', labelKey: 'nav.orders', icon: ReceiptText, end: false },
  { to: '/profile', labelKey: 'nav.profile', icon: User, end: false },
] as const;

/**
 * Mobile bottom navigation. Fixed to the viewport bottom with a safe-area
 * inset; pages reserve space with `.pb-nav-safe` / `.pb-combined-safe` so the
 * bar can never cover content or the footer.
 */
export function BottomNav() {
  const { itemCount } = useCart();
  const previewMode = useStorePreview();

  return (
    <nav
      aria-label={t('nav.primary')}
      className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-background/95 pb-[env(safe-area-inset-bottom)] shadow-navbar backdrop-blur md:hidden"
      style={{ height: 'calc(var(--bottom-nav-height) + env(safe-area-inset-bottom))' }}
    >
      <ul className="mx-auto flex h-[var(--bottom-nav-height)] max-w-lg items-stretch">
        {items
          .filter(({ to }) => !previewMode || to !== '/cart')
          .map(({ to, labelKey, icon: Icon, end }) => (
            <li key={to} className="flex-1">
              <NavLink
                to={to}
                end={end}
                className={({ isActive }) =>
                  cn(
                    'flex h-full flex-col items-center justify-center gap-1 text-[11px] font-medium',
                    isActive ? 'text-primary' : 'text-muted-foreground hover:text-foreground',
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <span className="relative">
                      <Icon
                        className="size-5"
                        aria-hidden="true"
                        strokeWidth={isActive ? 2.4 : 1.9}
                      />
                      {to === '/cart' && itemCount > 0 && (
                        <span
                          className="absolute -right-2 -top-1.5 min-w-4 rounded-full bg-primary px-1 text-center text-[10px] font-bold leading-4 text-primary-foreground"
                          aria-hidden="true"
                        >
                          {itemCount > 99 ? '99+' : itemCount}
                        </span>
                      )}
                    </span>
                    <span>
                      {t(labelKey)}
                      {to === '/cart' && itemCount > 0 && (
                        <span className="sr-only">, {itemCount} items</span>
                      )}
                    </span>
                  </>
                )}
              </NavLink>
            </li>
          ))}
      </ul>
    </nav>
  );
}
