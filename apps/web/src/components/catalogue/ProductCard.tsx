/**
 * Product card.
 *
 * Rules baked in here:
 *  * money is rendered from integer paise via `formatPaise` — never `toFixed`;
 *  * a missing image renders a deterministic monogram tile, not a stock photo,
 *    so the grid never shows the same placeholder picture for every product;
 *  * out-of-stock items stay visible but are not clickable into a dead end.
 */
import type { ProductCardOut } from '@tripat/api-client';
import { Star } from 'lucide-react';
import { Link } from 'react-router-dom';

import { Badge } from '@/components/ui/badge';
import { cn, discountPercent, formatPaise } from '@/lib/utils';

/** Brand-tinted tile derived from the product name, used when there is no photo. */
function monogram(name: string): { initials: string; tone: string } {
  const words = name.replace(/[^A-Za-z0-9 ]/g, ' ').split(/\s+/).filter(Boolean);
  const initials = words
    .slice(0, 2)
    .map((word) => word[0]?.toUpperCase() ?? '')
    .join('');
  const tones: [string, ...string[]] = [
    'from-amber-100 to-amber-200 text-amber-900',
    'from-emerald-100 to-emerald-200 text-emerald-900',
    'from-sky-100 to-sky-200 text-sky-900',
    'from-rose-100 to-rose-200 text-rose-900',
    'from-violet-100 to-violet-200 text-violet-900',
  ];
  let hash = 0;
  for (const char of name) hash = (hash * 31 + char.charCodeAt(0)) % 997;
  return { initials: initials || 'MSG', tone: tones[hash % tones.length] ?? tones[0] };
}

export function ProductThumb({
  name,
  imageUrl,
  className,
  size = 'md',
}: {
  name: string;
  imageUrl?: string | null;
  className?: string;
  size?: 'sm' | 'md' | 'lg';
}) {
  const tile = monogram(name);
  const text = size === 'lg' ? 'text-4xl' : size === 'sm' ? 'text-lg' : 'text-2xl';
  if (imageUrl) {
    return (
      <img
        src={imageUrl}
        alt={name}
        loading="lazy"
        decoding="async"
        className={cn('size-full object-cover', className)}
      />
    );
  }
  return (
    <div
      aria-hidden="true"
      className={cn(
        'flex size-full items-center justify-center bg-gradient-to-br font-semibold tracking-wide',
        tile.tone,
        text,
        className,
      )}
    >
      {tile.initials}
    </div>
  );
}

export function ProductCard({ product, priority = false }: { product: ProductCardOut; priority?: boolean }) {
  const off = product.discount_percent || discountPercent(product.mrp_paise, product.price_paise);
  const soldOut = !product.in_stock;
  const lowStock = product.in_stock && product.stock <= 5;

  return (
    <article
      className={cn(
        'group relative flex h-full flex-col overflow-hidden rounded-xl border border-border bg-card shadow-elev1 transition-shadow hover:shadow-elev2',
        soldOut && 'opacity-80',
      )}
    >
      <Link
        to={`/products/${product.slug}`}
        className="relative block aspect-square overflow-hidden bg-secondary"
        aria-label={`${product.name}, ${formatPaise(product.price_paise)} per ${product.unit_label}`}
      >
        <ProductThumb
          name={product.name}
          imageUrl={priority ? product.image_url : product.image_url}
        />
        {off > 0 && (
          <span className="absolute left-2 top-2 rounded-md bg-discount px-1.5 py-0.5 text-[11px] font-bold text-white">
            {off}% off
          </span>
        )}
        {soldOut && (
          <span className="absolute inset-0 flex items-center justify-center bg-background/75 text-sm font-semibold text-foreground">
            Out of stock
          </span>
        )}
      </Link>

      <div className="flex flex-1 flex-col gap-1 p-3">
        <p className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
          {product.brand_name ?? 'Loose · sold by weight'}
        </p>
        <h3 className="line-clamp-2 text-sm font-semibold leading-snug">
          <Link to={`/products/${product.slug}`} className="hover:text-primary-700">
            {product.name}
          </Link>
        </h3>
        <p className="text-xs text-muted-foreground">{product.unit_label}</p>

        <div className="mt-auto flex flex-wrap items-baseline gap-x-2 pt-1">
          <span className="text-base font-bold text-foreground">{formatPaise(product.price_paise)}</span>
          {product.mrp_paise > product.price_paise && (
            <span className="text-xs text-muted-foreground line-through">
              {formatPaise(product.mrp_paise)}
            </span>
          )}
        </div>

        <div className="flex items-center justify-between gap-2">
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Star className="size-3 fill-rating text-rating" aria-hidden="true" />
            {product.rating > 0 ? product.rating.toFixed(1) : 'New'}
            {product.has_variants && <span aria-hidden="true">· sizes</span>}
          </span>
          {lowStock && <Badge tone="warning">Only {product.stock} left</Badge>}
        </div>
      </div>
    </article>
  );
}
