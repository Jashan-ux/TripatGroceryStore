import type { ProductCardOut } from '@tripat/api-client';
import { ChevronRight } from 'lucide-react';
import { Link } from 'react-router-dom';

import { ProductCard } from '@/components/catalogue/ProductCard';
import { useReorderProducts } from '@/admin/adminCatalogue';
import { useAdminStoreView } from '@/features/store/StorePreviewContext';

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
  const isAdmin = useAdminStoreView();
  const reorder = useReorderProducts();
  if (products.length === 0) return null;
  const headingId = `rail-${href.replace(/[^a-z0-9]+/gi, '-')}`;

  const moveProduct = (index: number, direction: -1 | 1) => {
    const target = index + direction;
    if (target < 0 || target >= products.length || reorder.isPending) return;
    const ordered = [...products];
    [ordered[index], ordered[target]] = [ordered[target]!, ordered[index]!];
    reorder.mutate({ product_ids: ordered.map((product) => product.id) });
  };

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
        {products.map((product, index) => (
          <li key={product.id} className="w-[46%] shrink-0 xs:w-[44%] sm:w-[31%] lg:w-[23%]">
            <ProductCard
              product={product}
              onMoveLeft={isAdmin && index > 0 ? () => moveProduct(index, -1) : undefined}
              onMoveRight={
                isAdmin && index < products.length - 1 ? () => moveProduct(index, 1) : undefined
              }
              moving={reorder.isPending}
            />
          </li>
        ))}
      </ul>
      {isAdmin && (
        <p className="mt-1 text-xs text-muted-foreground">
          Use the arrows on a product to change its place in this shelf.
        </p>
      )}
      {reorder.isError && (
        <p role="alert" className="mt-2 text-xs text-warning">
          Could not save shelf order: {reorder.error.message}
        </p>
      )}
    </section>
  );
}
