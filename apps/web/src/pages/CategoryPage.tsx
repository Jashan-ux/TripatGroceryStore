import { PackageSearch } from 'lucide-react';
import { useEffect } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';

import type { CategoryTreeOut } from '@tripat/api-client';

import { CallStoreButton } from '@/components/common/CallStoreButton';
import { EmptyState } from '@/components/common/EmptyState';
import { Pagination } from '@/components/catalogue/Pagination';
import { ProductGrid, ProductGridSkeleton } from '@/components/catalogue/ProductGrid';
import { SortSelect } from '@/components/catalogue/SortSelect';
import { usePageTitle } from '@/hooks/usePageTitle';
import { useCategories, useProducts, type SortKey } from '@/features/catalogue/queries';
import { cn } from '@/lib/utils';
import { t } from '@/i18n';

const PAGE_SIZE = 24;

/**
 * Find a category by slug, whether it is a department or a department's child.
 * Cheap enough to run per render (one pass over ~40 rows) and it keeps the
 * component free of memoisation the React compiler would have to unpick.
 */
function findCategory(
  tree: CategoryTreeOut[] | undefined,
  slug: string,
): CategoryTreeOut | undefined {
  for (const parent of tree ?? []) {
    const children = parent.children ?? [];
    if (parent.slug === slug) return { ...parent, children };
    const child = children.find((entry) => entry.slug === slug);
    if (child) return { ...child, children: [] };
  }
  return undefined;
}

/**
 * Category listing. URL parameters are the state (`?sort=&page=`), so a shared
 * link reproduces exactly what the sender saw and back/forward behaves.
 */
export default function CategoryPage() {
  const { slug = '' } = useParams();
  const [params, setParams] = useSearchParams();
  const sort = (params.get('sort') as SortKey | null) ?? 'popular';
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1);
  const inStockOnly = params.get('in_stock') === 'true';

  const categories = useCategories();
  const category = findCategory(categories.data, slug);

  usePageTitle(category ? undefined : 'nav.category', category?.name);

  const products = useProducts({ category: slug, sort, page, pageSize: PAGE_SIZE, inStockOnly });

  // A page beyond the last one would show an empty grid — send the user back.
  useEffect(() => {
    if (products.data && products.data.total_pages > 0 && page > products.data.total_pages) {
      const next = new URLSearchParams(params);
      next.set('page', String(products.data.total_pages));
      setParams(next, { replace: true });
    }
  }, [products.data, page, params, setParams]);

  const update = (key: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value === null || value === '') next.delete(key);
    else next.set(key, value);
    if (key !== 'page') next.delete('page');
    setParams(next);
  };

  return (
    <div className="container py-5">
      <nav aria-label={t('catalogue.breadcrumb')} className="mb-2 text-xs text-muted-foreground">
        <Link to="/" className="hover:text-primary-700">
          {t('catalogue.home')}
        </Link>
        <span aria-hidden="true"> / </span>
        <span aria-current="page">{category?.name ?? t('catalogue.category')}</span>
      </nav>

      <header className="mb-4">
        <h1 className="text-xl font-extrabold tracking-tight sm:text-2xl">
          {category?.emoji ? `${category.emoji} ` : ''}
          {category?.name ?? t('catalogue.category')}
        </h1>
        {category?.description && (
          <p className="mt-1 text-sm text-muted-foreground">{category.description}</p>
        )}
        <p className="mt-1 text-sm text-muted-foreground" aria-live="polite">
          {products.data
            ? `${products.data.total} ${products.data.total === 1 ? t('catalogue.productCountOne') : t('catalogue.productCount')}`
            : t('catalogue.loading')}
        </p>
      </header>

      {category && (category.children ?? []).length > 0 && (
        <ul className="mb-4 flex flex-wrap gap-2">
          {(category.children ?? []).map((child) => (
            <li key={child.id}>
              <Link
                to={`/categories/${child.slug}`}
                className={cn(
                  'inline-flex min-h-touch items-center rounded-full border border-border bg-card px-3 text-sm font-medium hover:border-primary-300',
                  child.slug === slug && 'border-primary bg-primary-50 text-primary-800',
                )}
              >
                {child.name}
              </Link>
            </li>
          ))}
        </ul>
      )}

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <SortSelect value={sort} onChange={(value) => update('sort', value)} />
          <label className="inline-flex min-h-touch items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={inStockOnly}
              onChange={(event) => update('in_stock', event.target.checked ? 'true' : null)}
              className="size-4 rounded border-border"
            />
            {t('catalogue.inStockOnly')}
          </label>
        </div>
      </div>

      {products.isPending ? (
        <>
          <span className="sr-only" role="status">
            Loading products
          </span>
          <ProductGridSkeleton count={8} />
        </>
      ) : products.isError ? (
        <EmptyState
          icon={PackageSearch}
          title={t('catalogue.loadErrorTitle')}
          body={t('catalogue.loadErrorBody')}
          action={<CallStoreButton />}
        />
      ) : products.data && products.data.items.length === 0 ? (
        <EmptyState
          icon={PackageSearch}
          title={t('catalogue.emptyTitle')}
          body={t('catalogue.emptyBody')}
          action={<CallStoreButton />}
        />
      ) : (
        <>
          <ProductGrid products={products.data?.items ?? []} />
          <Pagination
            page={page}
            totalPages={products.data?.total_pages ?? 0}
            onChange={(nextPage) => update('page', String(nextPage))}
          />
        </>
      )}
    </div>
  );
}
