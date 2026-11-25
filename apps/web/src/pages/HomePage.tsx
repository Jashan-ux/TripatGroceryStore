import { useQuery } from '@tanstack/react-query';
import type { HealthResponse } from '@tripat/api-client';
import { MapPin, PackageOpen, Sparkles, Store } from 'lucide-react';
import { Link } from 'react-router-dom';

import { CallStoreButton } from '@/components/common/CallStoreButton';
import { EmptyState } from '@/components/common/EmptyState';
import { CategoryGrid } from '@/components/catalogue/CategoryGrid';
import { ProductRail } from '@/components/catalogue/ProductRail';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ProductRailSkeleton } from '@/components/ui/skeleton';
import { useHome } from '@/features/catalogue/queries';
import { usePageTitle } from '@/hooks/usePageTitle';
import { useStoreConfig } from '@/hooks/useStoreConfig';
import { t } from '@/i18n';
import { api } from '@/lib/api';
import { formatPaise } from '@/lib/utils';

/** Health probe drives the "store online" indicator in the hero. */
function useStoreHealth() {
  return useQuery<HealthResponse>({
    queryKey: ['health'],
    queryFn: ({ signal }) => api.get<HealthResponse>('/healthz', { signal }),
    staleTime: 60_000,
    retry: 1,
  });
}

export default function HomePage() {
  usePageTitle();
  const config = useStoreConfig();
  const health = useStoreHealth();
  const home = useHome();

  return (
    <div className="pb-8">
      {/* Hero: brand banner with the store promise and a tap-to-call action. */}
      <section aria-labelledby="hero-heading" className="container pt-3">
        <div className="overflow-hidden rounded-2xl bg-gradient-to-br from-primary-700 via-primary-700 to-primary-900 text-white shadow-elev2">
          <div className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-7">
            <div className="max-w-xl space-y-2">
              <Badge className="bg-white/15 text-white" tone="neutral">
                <Sparkles className="size-3" aria-hidden="true" />
                {config.data?.store_name ?? t('brand.full')}
              </Badge>
              <h1
                id="hero-heading"
                className="text-balance text-2xl font-extrabold leading-tight sm:text-3xl"
              >
                {t('home.bannerTitle')}
              </h1>
              <p className="text-sm text-white/85">{t('home.bannerSubtitle')}</p>
              {config.data && (
                <p className="text-xs text-white/80">
                  Minimum order {formatPaise(config.data.minimum_order_paise)} · Cash on delivery ·
                  Delivered in {config.data.default_delivery_days} day
                </p>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <CallStoreButton className="border-transparent bg-white text-primary-800 hover:bg-primary-50" />
              {config.data?.store_maps_url ? (
                <Button asChild variant="ghost" className="text-white hover:bg-white/15 hover:text-white">
                  <a href={config.data.store_maps_url} target="_blank" rel="noreferrer noopener">
                    <MapPin aria-hidden="true" />
                    Open in Maps
                  </a>
                </Button>
              ) : null}
            </div>
          </div>
        </div>
      </section>

      {/* Store status strip: address + live health, from server settings. */}
      <section aria-label="Store information" className="container mt-3">
        <div className="flex flex-wrap items-center gap-x-4 gap-y-2 rounded-xl bg-muted/60 px-4 py-3 text-sm text-muted-foreground">
          <span className="inline-flex items-center gap-1.5 font-medium text-foreground">
            <Store className="size-4 text-primary" aria-hidden="true" />
            {t('footer.openNow')}
          </span>
          {health.data ? (
            <span>{health.data.status === 'ok' ? 'Store online' : 'Store partially available'}</span>
          ) : null}
          {config.data ? <span className="hidden sm:inline">{config.data.store_address}</span> : null}
        </div>
      </section>

      {home.isPending ? (
        <div className="container pt-6">
          <span className="sr-only" role="status">
            {t('home.loadingCatalogue')}
          </span>
          <ProductRailSkeleton />
          <div className="mt-6">
            <ProductRailSkeleton />
          </div>
        </div>
      ) : home.isError || !home.data || home.data.rails.length === 0 ? (
        <section aria-labelledby="catalogue-heading" className="container mt-6">
          <h2 id="catalogue-heading" className="mb-3 text-lg font-bold">
            {t('home.shopByCategory')}
          </h2>
          <EmptyState
            icon={PackageOpen}
            title={t('home.catalogueEmptyTitle')}
            body={t('home.catalogueEmptyBody')}
            action={<CallStoreButton />}
          />
        </section>
      ) : (
        <>
          <CategoryGrid categories={home.data.categories} />
          {home.data.rails.slice(0, 4).map((rail) => (
            <ProductRail
              key={rail.category.id}
              title={`${rail.category.emoji ?? ''} ${rail.category.name}`.trim()}
              subtitle={rail.category.description ?? undefined}
              href={`/categories/${rail.category.slug}`}
              products={rail.products}
            />
          ))}
          <section className="container pt-6">
            <div className="flex flex-col items-start gap-2 rounded-2xl border border-dashed border-border bg-card p-5 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h2 className="text-base font-bold">Looking for something else?</h2>
                <p className="text-sm text-muted-foreground">
                  Our full catalogue runs to thousands of items. Tell us what you need and we will
                  keep it ready.
                </p>
              </div>
              <div className="flex gap-2">
                <CallStoreButton />
                <Button asChild variant="outline">
                  <Link to="/search">Search the store</Link>
                </Button>
              </div>
            </div>
          </section>
        </>
      )}
    </div>
  );
}
