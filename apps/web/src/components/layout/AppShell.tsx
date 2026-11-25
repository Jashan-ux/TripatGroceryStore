import { Outlet, useLocation } from 'react-router-dom';

import { OfflineBanner } from '@/components/common/OfflineBanner';
import { UpdatePrompt } from '@/components/common/UpdatePrompt';
import { BottomNav } from '@/components/layout/BottomNav';
import { SiteFooter } from '@/components/layout/SiteFooter';
import { SiteHeader } from '@/components/layout/SiteHeader';
import { t } from '@/i18n';
import { cn } from '@/lib/utils';

/**
 * Storefront shell.
 *
 * Spacing contract (the fix for the "bottom nav overlaps content" defect):
 * the footer's last row carries `.pb-nav-safe`, so the fixed bottom nav plus the
 * safe-area inset always clear the final line of content. Pages that add the
 * sticky cart bar use `.pb-combined-safe` on their own container.
 */
export function AppShell() {
  const location = useLocation();

  return (
    <div className="flex min-h-dvh flex-col">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-2 focus:top-2 focus:z-50 focus:rounded-lg focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
      >
        {t('nav.skipToContent')}
      </a>
      <UpdatePrompt />
      <OfflineBanner />
      <SiteHeader />
      <main id="main" tabIndex={-1} className={cn('flex-1 outline-none')}>
        <div key={location.pathname} className="animate-none">
          <Outlet />
        </div>
      </main>
      <SiteFooter />
      <BottomNav />
    </div>
  );
}
