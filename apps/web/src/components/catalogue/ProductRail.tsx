import type { ProductCardOut } from '@tripat/api-client';
import { ChevronRight } from 'lucide-react';
import { Link } from 'react-router-dom';

import { ProductCard } from '@/components/catalogue/ProductCard';

/**
 * Horizontally scrolling rail. It is a real list (`<ul>`) so screen readers
 * announce "list, 8 items", and the heading links to the full category page.
 */
export function ProductRail({
  title,
  subtitle,
  href,
  products,
}: {
  title: string;
  subtitle?: string;
  href: string;
  products: ProductCardOut[];
}) {
  if (products.length === 0) return null;
  const headingId = `rail-${href.replace(/[^a-z0-9]+/gi, '-')}`;

  return (
    <section aria-labelledby={headingId} className="container pt-6">
      <div className="mb-3 flex items-end justify-between gap-3">
        <div>
          <h2 id={headingId} className="text-base font-bold tracking-tight sm:text-lg">
            {title}
          </h2>
          {subtitle && <p className="text-xs text-muted-foreground sm:text-sm">{subtitle}</p>}
        </div>
        <Link
          to={href}
          className="inline-flex min-h-touch items-center gap-0.5 text-sm font-semibold text-primary-700 hover:text-primary-900"
        >
          See all
          <ChevronRight className="size-4" aria-hidden="true" />
        </Link>
      </div>
      <ul className="rail -mx-1 px-1">
        {products.map((product) => (
          <li key={product.id} className="w-[46%] shrink-0 xs:w-[44%] sm:w-[31%] lg:w-[23%]">
            <ProductCard product={product} />
          </li>
        ))}
      </ul>
    </section>
  );
}
