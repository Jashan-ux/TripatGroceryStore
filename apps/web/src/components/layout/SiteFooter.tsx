import { Link } from 'react-router-dom';

import { BrandMark } from '@/components/common/BrandMark';
import { useStoreConfig } from '@/hooks/useStoreConfig';
import { t } from '@/i18n';
import { toTelHref } from '@/lib/utils';

const shopLinks = [
  { to: '/categories', labelKey: 'home.shopByCategory' },
  { to: '/search', labelKey: 'nav.search' },
  { to: '/orders', labelKey: 'footer.orderHistory' },
];

const serviceLinks = [
  { to: '/contact', labelKey: 'footer.contactUs' },
  { to: '/policies/shipping', labelKey: 'footer.shippingInfo' },
  { to: '/policies/returns', labelKey: 'footer.returns' },
  { to: '/policies/faq', labelKey: 'footer.faq' },
];

const accountLinks = [
  { to: '/profile', labelKey: 'footer.myProfile' },
  { to: '/orders', labelKey: 'footer.orderHistory' },
  { to: '/rewards', labelKey: 'footer.rewards' },
];

/**
 * Customer footer. Not rendered inside admin (defect 6.4). On mobile it sits
 * above the bottom nav thanks to `.pb-nav-safe` on the page container, so links
 * are always reachable.
 */
export function SiteFooter() {
  const { data } = useStoreConfig();
  const year = new Date().getFullYear();

  return (
    <footer className="mt-10 border-t border-border bg-muted/40">
      <div className="container grid gap-8 py-8 sm:grid-cols-2 lg:grid-cols-4">
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <BrandMark decorative />
            <div>
              <p className="text-base font-extrabold text-primary">{t('brand.name')}</p>
              <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-muted-foreground">
                MSG Store
              </p>
            </div>
          </div>
          <p className="text-sm text-muted-foreground">{t('footer.about')}</p>
          <div className="min-h-16 md:min-h-0">
            {data ? (
              <address className="space-y-1 text-sm not-italic text-muted-foreground">
                <a className="block font-medium text-foreground" href={toTelHref(data.store_phone)}>
                  {data.store_phone}
                </a>
                <span className="block">{data.store_address}</span>
              </address>
            ) : null}
          </div>
        </div>

        <FooterColumn title={t('footer.shop')} links={shopLinks} />
        <FooterColumn title={t('footer.customerService')} links={serviceLinks} />
        <FooterColumn title={t('footer.account')} links={accountLinks} />
      </div>

      <div className="border-t border-border">
        <div className="container flex flex-col gap-2 pb-nav-safe pt-4 text-xs text-muted-foreground sm:flex-row sm:items-center sm:justify-between md:pb-4">
          <p>
            © {year} {t('brand.full')}. {t('footer.rights')}
          </p>
          <div className="flex flex-wrap items-center gap-4">
            <Link to="/policies/privacy" className="hover:text-foreground hover:underline">
              {t('footer.privacy')}
            </Link>
            <Link to="/policies/terms" className="hover:text-foreground hover:underline">
              {t('footer.terms')}
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}

function FooterColumn({
  title,
  links,
}: {
  title: string;
  links: readonly { to: string; labelKey: string }[];
}) {
  return (
    <nav aria-label={title}>
      <h2 className="mb-3 text-sm font-semibold uppercase tracking-wide text-foreground">
        {title}
      </h2>
      <ul className="space-y-2">
        {links.map(({ to, labelKey }) => (
          <li key={`${to}-${labelKey}`}>
            <Link
              to={to}
              className="inline-flex min-h-touch items-center text-sm text-muted-foreground hover:text-foreground hover:underline"
            >
              {t(labelKey)}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
