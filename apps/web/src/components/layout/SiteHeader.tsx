import { Bell, Menu, Search, ShoppingCart, User } from 'lucide-react';
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';

import { BrandMark, Wordmark } from '@/components/common/BrandMark';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { t } from '@/i18n';

/**
 * Storefront header: logo + wordmark, then search, then the action cluster.
 * Sticky and translucent so it never pushes content around, and never taller
 * than two rows at 360px so the product grid keeps the viewport.
 */
export function SiteHeader() {
  const navigate = useNavigate();
  const [term, setTerm] = useState('');

  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/85">
      <div className="container flex items-center gap-2 py-2">
        <Link
          to="/"
          className="flex items-center gap-2 rounded-xl focus-visible:outline-none"
          aria-label={t('brand.full')}
        >
          <BrandMark decorative />
          <Wordmark className="hidden xs:flex" />
          <span className="sr-only xs:hidden">{t('brand.full')}</span>
        </Link>

        <nav aria-label={t('nav.primary')} className="ml-auto flex items-center gap-0.5">
          <Button asChild variant="ghost" size="icon" aria-label={t('nav.notifications')}>
            <Link to="/notifications">
              <Bell aria-hidden="true" />
            </Link>
          </Button>
          <Button asChild variant="ghost" size="icon" aria-label={t('nav.profile')}>
            <Link to="/profile">
              <User aria-hidden="true" />
            </Link>
          </Button>
          <Button asChild variant="ghost" size="icon" aria-label={t('nav.cart')}>
            <Link to="/cart">
              <ShoppingCart aria-hidden="true" />
            </Link>
          </Button>
          <Button asChild variant="ghost" size="icon" aria-label={t('nav.menu')}>
            <Link to="/menu">
              <Menu aria-hidden="true" />
            </Link>
          </Button>
        </nav>
      </div>

      <div className="container pb-2">
        <form
          role="search"
          className="relative"
          onSubmit={(event) => {
            event.preventDefault();
            const query = term.trim();
            navigate(query ? `/search?q=${encodeURIComponent(query)}` : '/search');
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
