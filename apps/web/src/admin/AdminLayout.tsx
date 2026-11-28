import { ArrowUpRight, Store } from 'lucide-react';
import { NavLink, Outlet } from 'react-router-dom';

import { adminSections } from '@/admin/adminSections';
import { BrandMark } from '@/components/common/BrandMark';
import { LanguageSelector } from '@/components/common/LanguageSelector';
import { useUnreadCount } from '@/features/notifications/queries';
import { Button } from '@/components/ui/button';
import { t } from '@/i18n';
import { cn } from '@/lib/utils';

const SIDEBAR_GROUPS = [
  { label: 'Daily work', routes: ['/admin', '/admin/orders'] },
  {
    label: 'Products & stock',
    routes: ['/admin/products', '/admin/inventory', '/admin/categories', '/admin/brands'],
  },
  { label: 'Customers & growth', routes: ['/admin/customers', '/admin/returns', '/admin/offers'] },
  { label: 'Store management', routes: ['/admin/feedback', '/admin/activity', '/admin/settings'] },
] as const;

const MOBILE_ROUTES = new Set([
  '/admin',
  '/admin/orders',
  '/admin/products',
  '/admin/inventory',
  '/admin/customers',
  '/admin/settings',
]);

/**
 * Merchant-only workspace. The desktop sidebar groups operational tasks, while
 * tablets keep a compact horizontal strip and phones get the thumb-friendly nav.
 * This route stays in the lazy admin bundle and never renders customer cart UI.
 */
export function AdminLayout() {
  const unread = useUnreadCount().data?.unread_count ?? 0;
  const mobileSections = adminSections.filter((section) => MOBILE_ROUTES.has(section.to));
  const tabletSections = mobileSections;

  return (
    <div className="flex min-h-dvh flex-col bg-muted/30">
      <header className="sticky top-0 z-40 border-b border-border bg-background/95 shadow-sm backdrop-blur">
        <div className="container flex min-h-16 max-w-screen-2xl items-center gap-3 py-2">
          <BrandMark decorative className="size-10 shrink-0" />
          <div className="min-w-0">
            <p className="truncate text-sm font-extrabold text-primary">{t('brand.name')}</p>
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-muted-foreground">
              Merchant workspace
            </p>
          </div>
          <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
            <LanguageSelector />
            <Button asChild variant="outline" size="sm" className="px-2.5 sm:px-3">
              <NavLink
                to="/?preview=1"
                aria-label="Preview storefront as a customer"
                className="inline-flex items-center gap-2"
              >
                <Store className="size-4" aria-hidden="true" />
                <span className="hidden sm:inline">Preview store</span>
                <ArrowUpRight className="hidden size-3.5 sm:inline" aria-hidden="true" />
              </NavLink>
            </Button>
          </div>
        </div>
      </header>

      <nav
        aria-label="Merchant navigation"
        className="hidden border-b border-border bg-background md:block lg:hidden"
      >
        <ul className="container flex max-w-screen-2xl items-stretch gap-1 overflow-x-auto">
          {tabletSections.map((section) => (
            <li key={section.to}>
              <AdminNavLink section={section} unread={unread} compact />
            </li>
          ))}
        </ul>
      </nav>

      <div className="container flex w-full max-w-screen-2xl flex-1 gap-6 py-5 pb-nav-safe md:pb-6">
        <aside className="hidden w-60 shrink-0 lg:block" aria-label="Merchant sections">
          <div className="sticky top-24 space-y-5 rounded-2xl border border-border bg-card p-3 shadow-elev1">
            <div className="rounded-xl bg-primary/5 px-3 py-3">
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-primary">
                Store admin
              </p>
              <p className="mt-1 text-sm font-bold">Daily operations</p>
              <p className="mt-0.5 text-xs text-muted-foreground">Manage the shop from here.</p>
            </div>
            <nav aria-label="Merchant navigation" className="space-y-5">
              {SIDEBAR_GROUPS.map((group) => {
                const routes = new Set<string>(group.routes);
                return (
                  <div key={group.label}>
                    <h2 className="mb-1 px-3 text-[10px] font-bold uppercase tracking-[0.16em] text-muted-foreground">
                      {group.label}
                    </h2>
                    <ul className="space-y-0.5">
                      {adminSections
                        .filter((section) => routes.has(section.to))
                        .map((section) => (
                          <li key={section.to}>
                            <AdminNavLink section={section} unread={unread} />
                          </li>
                        ))}
                    </ul>
                  </div>
                );
              })}
            </nav>
          </div>
        </aside>

        <main className="min-w-0 flex-1">
          <Outlet />
        </main>
      </div>

      <nav
        aria-label="Merchant navigation"
        className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-background/95 pb-[env(safe-area-inset-bottom)] shadow-navbar backdrop-blur md:hidden"
        style={{ height: 'calc(var(--bottom-nav-height) + env(safe-area-inset-bottom))' }}
      >
        <ul className="mx-auto flex h-[var(--bottom-nav-height)] max-w-lg items-stretch">
          {mobileSections.map((section) => (
            <li key={section.to} className="flex-1">
              <AdminNavLink section={section} unread={unread} mobile />
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}

function AdminNavLink({
  section,
  unread,
  compact = false,
  mobile = false,
}: {
  section: (typeof adminSections)[number];
  unread: number;
  compact?: boolean;
  mobile?: boolean;
}) {
  const Icon = section.icon;
  return (
    <NavLink
      to={section.to}
      end={section.end}
      className={({ isActive }) =>
        cn(
          mobile
            ? 'flex h-full flex-col items-center justify-center gap-1 text-[10px] font-semibold'
            : compact
              ? 'inline-flex min-h-touch items-center gap-2 rounded-lg px-3 text-sm font-semibold'
              : 'flex min-h-10 items-center gap-2 rounded-lg px-3 text-sm font-semibold',
          isActive
            ? 'bg-primary/10 text-primary'
            : 'text-muted-foreground hover:bg-muted hover:text-foreground',
        )
      }
    >
      <span className="relative">
        <Icon className={mobile ? 'size-5' : 'size-4'} aria-hidden="true" />
        {section.to === '/admin/orders' && unread > 0 && (
          <span
            className={cn(
              'rounded-full bg-destructive text-center text-[10px] font-bold leading-4 text-destructive-foreground',
              mobile
                ? 'absolute -right-2 -top-1.5 min-w-4 px-1'
                : compact
                  ? 'ml-1 min-w-4 px-1'
                  : 'ml-auto min-w-5 px-1.5',
            )}
            aria-label={`${unread} unread`}
          >
            {unread > 99 ? '99+' : unread}
          </span>
        )}
      </span>
      <span>{t(section.labelKey)}</span>
      {mobile && section.to === '/admin/orders' && unread > 0 && (
        <span className="sr-only">, {unread} unread</span>
      )}
    </NavLink>
  );
}
