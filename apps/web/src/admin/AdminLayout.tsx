import { Store } from 'lucide-react';
import { NavLink, Outlet } from 'react-router-dom';

import { adminSections } from '@/admin/adminSections';
import { BrandMark } from '@/components/common/BrandMark';
import { t } from '@/i18n';
import { cn } from '@/lib/utils';

/**
 * Admin shell: deliberately has **no** cart, no customer footer and no product
 * search bar (defect 6.4). Everything here lives in the lazily-loaded admin
 * bundle so no admin code ships to customers.
 */
export function AdminLayout() {
  return (
    <div className="flex min-h-dvh flex-col bg-muted/30">
      <header className="sticky top-0 z-40 border-b border-border bg-background">
        <div className="container flex items-center gap-3 py-2.5">
          <BrandMark decorative className="size-9" />
          <div className="min-w-0">
            <p className="truncate text-sm font-extrabold text-primary">{t('brand.name')}</p>
            <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
              {t('admin.title')}
            </p>
          </div>
          <NavLink
            to="/"
            className="ml-auto inline-flex min-h-touch items-center gap-2 rounded-xl px-3 text-sm font-semibold text-foreground hover:bg-secondary"
          >
            <Store className="size-4" aria-hidden="true" />
            <span className="hidden sm:inline">Catalog</span>
          </NavLink>
        </div>

        <nav aria-label={t('admin.title')} className="hidden border-t border-border md:block">
          <ul className="container flex items-stretch gap-1 overflow-x-auto">
            {adminSections.map(({ to, labelKey, icon: Icon, end }) => (
              <li key={to}>
                <NavLink
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    cn(
                      'inline-flex min-h-touch items-center gap-2 border-b-2 px-3 text-sm font-medium',
                      isActive
                        ? 'border-primary text-primary'
                        : 'border-transparent text-muted-foreground hover:text-foreground',
                    )
                  }
                >
                  <Icon className="size-4" aria-hidden="true" />
                  {t(labelKey)}
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
      </header>

      <main className="container w-full flex-1 py-4 pb-nav-safe md:pb-6">
        <Outlet />
      </main>

      <nav
        aria-label={t('admin.title')}
        className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-background/95 pb-[env(safe-area-inset-bottom)] shadow-navbar backdrop-blur md:hidden"
        style={{ height: 'calc(var(--bottom-nav-height) + env(safe-area-inset-bottom))' }}
      >
        <ul className="mx-auto flex h-[var(--bottom-nav-height)] max-w-lg items-stretch">
          {adminSections
            .filter((section) => section.mobile)
            .map(({ to, labelKey, icon: Icon, end }) => (
              <li key={to} className="flex-1">
                <NavLink
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    cn(
                      'flex h-full flex-col items-center justify-center gap-1 text-[11px] font-medium',
                      isActive ? 'text-primary' : 'text-muted-foreground',
                    )
                  }
                >
                  <Icon className="size-5" aria-hidden="true" />
                  <span>{t(labelKey)}</span>
                </NavLink>
              </li>
            ))}
        </ul>
      </nav>
    </div>
  );
}
