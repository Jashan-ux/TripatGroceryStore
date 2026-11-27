import type { VariantOut } from '@tripat/api-client';
import { Check, ChevronLeft, Phone, ShieldCheck, Star, Truck } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';

import { AddToCart } from '@/components/cart/AddToCart';
import { CallStoreButton } from '@/components/common/CallStoreButton';
import { EmptyState } from '@/components/common/EmptyState';
import { ProductThumb } from '@/components/catalogue/ProductCard';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { useProduct } from '@/features/catalogue/queries';
import { usePageTitle } from '@/hooks/usePageTitle';
import { useStoreConfig } from '@/hooks/useStoreConfig';
import { cn, discountPercent, formatPaise } from '@/lib/utils';
import { t } from '@/i18n';

/**
 * Product detail.
 *
 * Adding to the cart is the primary action; calling the store stays available as
 * the secondary one for shoppers who would rather ask first.
 */
export default function ProductPage() {
  const { slug } = useParams();
  const product = useProduct(slug);
  usePageTitle(undefined, product.data?.name ?? 'Product');

  const config = useStoreConfig();
  const [variantId, setVariantId] = useState<string | null>(null);
  const [activeImage, setActiveImage] = useState(0);

  const variants = useMemo<VariantOut[]>(() => product.data?.variants ?? [], [product.data]);
  const selectedVariant = useMemo(() => {
    if (variants.length === 0) return null;
    return variants.find((variant) => variant.id === variantId) ?? variants[0];
  }, [variantId, variants]);

  if (product.isPending) {
    return (
      <div className="container space-y-4 py-6">
        <Skeleton className="aspect-square w-full rounded-2xl sm:max-w-sm" />
        <Skeleton className="h-6 w-2/3" />
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (product.isError || !product.data) {
    return (
      <div className="container py-8">
        <EmptyState
          icon={Phone}
          title={t('catalogue.productNotFound')}
          body={t('catalogue.productNotFoundBody')}
          action={<CallStoreButton />}
        />
      </div>
    );
  }

  const item = product.data;
  const pricePaise = selectedVariant?.price_paise ?? item.price_paise;
  const mrpPaise = selectedVariant?.mrp_paise ?? item.mrp_paise;
  const stock = selectedVariant?.stock ?? item.stock;
  const off = discountPercent(mrpPaise, pricePaise);
  const images = item.images?.length ? item.images : [null];

  return (
    <div className="container py-5">
      <Link
        to={`/categories/${item.category_slug}`}
        className="mb-3 inline-flex min-h-touch items-center gap-1 text-sm font-medium text-muted-foreground hover:text-primary-700"
      >
        <ChevronLeft className="size-4" aria-hidden="true" />
        {item.category_name || t('catalogue.backToCategory')}
      </Link>

      <div className="grid gap-6 lg:grid-cols-2">
        <div>
          <div className="aspect-square overflow-hidden rounded-2xl border border-border bg-secondary">
            <ProductThumb name={item.name} imageUrl={images[activeImage]} size="lg" />
          </div>
          {images.length > 1 && (
            <ul className="mt-2 flex gap-2">
              {images.map((image, index) => (
                <li key={image ?? index}>
                  <button
                    type="button"
                    onClick={() => setActiveImage(index)}
                    aria-label={`${t('catalogue.imageLabel')} ${index + 1}`}
                    aria-current={index === activeImage}
                    className={cn(
                      'size-14 overflow-hidden rounded-lg border-2',
                      index === activeImage ? 'border-primary' : 'border-transparent',
                    )}
                  >
                    <ProductThumb name={item.name} imageUrl={image} size="sm" />
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="space-y-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {item.brand_name ?? t('catalogue.looseAtCounter')}
            </p>
            <h1 className="mt-1 text-balance text-2xl font-extrabold leading-tight">{item.name}</h1>
            <div className="mt-1.5 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <Star className="size-3.5 fill-rating text-rating" aria-hidden="true" />
                {item.rating > 0 ? `${item.rating.toFixed(1)} / 5` : t('catalogue.newArrival')}
              </span>
              <span aria-hidden="true">·</span>
              <span>{item.unit_label}</span>
              {(item.tags ?? []).slice(0, 2).map((tag) => (
                <Badge key={tag} tone="neutral">
                  {tag.replace(/-/g, ' ')}
                </Badge>
              ))}
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-4">
            <div className="flex flex-wrap items-baseline gap-2">
              <span className="text-2xl font-extrabold">{formatPaise(pricePaise)}</span>
              {mrpPaise > pricePaise && (
                <>
                  <span className="text-sm text-muted-foreground line-through">
                    {formatPaise(mrpPaise)}
                  </span>
                  <Badge tone="success">
                    {off}% {t('catalogue.discountOff')}
                  </Badge>
                </>
              )}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {t('catalogue.inclusiveTaxes')} ·{' '}
              {stock > 0 ? `${stock} ${t('catalogue.inStock')}` : t('catalogue.outOfStock')}
            </p>

            {variants.length > 1 && (
              <fieldset className="mt-4">
                <legend className="mb-2 text-sm font-semibold">{t('catalogue.choosePack')}</legend>
                <div className="flex flex-wrap gap-2">
                  {variants.map((variant) => {
                    const active = variant.id === selectedVariant?.id;
                    return (
                      <button
                        key={variant.id}
                        type="button"
                        onClick={() => setVariantId(variant.id)}
                        aria-pressed={active}
                        disabled={variant.stock === 0}
                        className={cn(
                          'min-h-touch rounded-xl border px-3 py-2 text-left text-sm disabled:opacity-50',
                          active
                            ? 'border-primary bg-primary-50 text-primary-900'
                            : 'border-border bg-background hover:border-primary-300',
                        )}
                      >
                        <span className="flex items-center gap-1 font-semibold">
                          {active && <Check className="size-3.5" aria-hidden="true" />}
                          {variant.label}
                        </span>
                        <span className="block text-xs text-muted-foreground">
                          {formatPaise(variant.price_paise)}
                          {variant.stock === 0 ? ` · ${t('catalogue.outOfStock')}` : ''}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </fieldset>
            )}

            <div className="mt-4">
              <AddToCart
                size="md"
                className="w-full"
                label={t('catalogue.addToCart')}
                disabledReason={stock === 0 ? t('catalogue.outOfStock') : undefined}
                line={{
                  productId: item.id,
                  variantId: selectedVariant?.id ?? null,
                  slug: item.slug,
                  name: item.name,
                  unitLabel: item.unit_label,
                  variantLabel: selectedVariant?.label ?? '',
                  imageUrl: item.image_url ?? null,
                  pricePaise,
                  maxQuantity: stock,
                }}
              />
            </div>

            <div className="mt-2 flex flex-col gap-2 sm:flex-row">
              <CallStoreButton className="sm:flex-1" />
              {config.data?.store_maps_url && (
                <a
                  href={config.data.store_maps_url}
                  target="_blank"
                  rel="noreferrer noopener"
                  className="inline-flex min-h-touch items-center justify-center rounded-xl border border-border px-4 text-sm font-semibold hover:bg-secondary"
                >
                  {t('catalogue.getDirections')}
                </a>
              )}
            </div>
            <p className="mt-2 text-center text-xs text-muted-foreground">
              Cash on delivery · no delivery charge. Prefer to talk? Call the store.
            </p>
          </div>

          <ul className="grid gap-2 text-sm sm:grid-cols-2">
            <li className="flex items-start gap-2 rounded-lg bg-muted/60 p-3">
              <Truck className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
              <span>
                Delivered in {config.data?.default_delivery_days ?? 1} day within Mandi Dabwali
                {config.data ? ` (${(config.data.serviceable_pincodes ?? []).join(', ')})` : ''}
              </span>
            </li>
            <li className="flex items-start gap-2 rounded-lg bg-muted/60 p-3">
              <ShieldCheck className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
              <span>Cash on delivery. No delivery charge.</span>
            </li>
          </ul>

          {item.description && (
            <section aria-labelledby="description-heading">
              <h2 id="description-heading" className="mb-1 text-sm font-bold">
                About this product
              </h2>
              <p className="text-sm leading-relaxed text-muted-foreground">{item.description}</p>
            </section>
          )}
        </div>
      </div>
    </div>
  );
}
