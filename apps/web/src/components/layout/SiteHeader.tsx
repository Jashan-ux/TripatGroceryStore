import { Boxes, ClipboardList, Menu, Search, ShoppingCart, User } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { BrandMark, Wordmark } from '@/components/common/BrandMark';
import { LanguageSelector } from '@/components/common/LanguageSelector';
import { NotificationBell } from '@/components/layout/NotificationBell';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/features/auth/useAuth';
import { useAdminStoreView } from '@/features/store/StorePreviewContext';
import { useCart } from '@/features/cart/useCart';
import { t } from '@/i18n';

/**
 * Storefront header: logo + wordmark, then search, then the action cluster.
 * Sticky and translucent so it never pushes content around, and never taller
 * than two rows at 360px so the product grid keeps the viewport.
 */
export function SiteHeader() {
  const navigate = useNavigate();
  const [term, setTerm] = useState('');
  const { status, profile } = useAuth();
  const { itemCount } = useCart();
  const adminStoreMode = useAdminStoreView();

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/85">
      <div className="container flex items-center gap-2 py-2">
        <Link to="/" className="flex items-center gap-2 rounded-xl focus-visible:outline-none">
          <BrandMark decorative />
          <Wordmark className="hidden sm:flex" />
          <span className="sr-only sm:hidden">{t('brand.full')}</span>
        </Link>

        <nav aria-label={t('nav.primary')} className="ml-auto flex items-center gap-0.5">
          <LanguageSelector />
          {adminStoreMode ? (
            <Button asChild variant="ghost" size="icon" aria-label="Orders">
              <Link to="/admin/orders">
                <ClipboardList aria-hidden="true" />
              </Link>
            </Button>
          ) : (
            <>
              <NotificationBell />
              <Button
                asChild
                variant="ghost"
                size="icon"
                aria-label={
                  status === 'authenticated' ? `${profile?.name || 'My account'}` : t('nav.profile')
                }
              >
                <Link to={status === 'authenticated' ? '/profile' : '/sign-in'}>
                  <User aria-hidden="true" />
                </Link>
              </Button>
            </>
          )}
          {/* Cart is in the bottom nav on phones: keeping both would overflow 360px. */}
          {!adminStoreMode && (
            <Button
              asChild
              variant="ghost"
              size="icon"
              aria-label={t('nav.cart')}
              className="hidden sm:inline-flex"
            >
              <Link to="/cart" className="relative">
                <ShoppingCart aria-hidden="true" />
                {itemCount > 0 && (
                  <span
                    className="absolute -right-1 -top-1 min-w-4 rounded-full bg-primary px-1 text-center text-[10px] font-bold leading-4 text-primary-foreground"
                    aria-hidden="true"
                  >
                    {itemCount > 99 ? '99+' : itemCount}
                  </span>
                )}
              </Link>
            </Button>
          )}
          {adminStoreMode ? (
            <Button asChild variant="ghost" size="icon" aria-label="Products">
              <Link to="/admin/products">
                <Boxes aria-hidden="true" />
              </Link>
            </Button>
          ) : (
            <Button asChild variant="ghost" size="icon" aria-label={t('nav.menu')}>
              <Link to="/menu">
                <Menu aria-hidden="true" />
              </Link>
            </Button>
          )}
        </nav>
      </div>

      <div className="container pb-2">
        <form
          role="search"
          className="relative"
          onSubmit={(event) => {
            event.preventDefault();
            const query = term.trim();
            void navigate(query ? `/search?q=${encodeURIComponent(query)}` : '/search');
          }}
        >
          <label htmlFor="store-search" className="sr-only">
            {t('search.label')}
          </label>
          <Search
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            id="store-search"
            name="q"
            type="search"
            inputMode="search"
            autoComplete="off"
            enterKeyHint="search"
            placeholder={t('search.placeholder')}
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            className="pl-9"
          />
        </form>
      </div>
    </header>
  );
}
