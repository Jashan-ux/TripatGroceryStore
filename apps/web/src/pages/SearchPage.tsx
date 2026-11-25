import { SearchX, Search as SearchIcon } from 'lucide-react';
import { useDeferredValue } from 'react';
import { Link, useSearchParams } from 'react-router-dom';

import { CallStoreButton } from '@/components/common/CallStoreButton';
import { EmptyState } from '@/components/common/EmptyState';
import { Pagination } from '@/components/catalogue/Pagination';
import { ProductGrid, ProductGridSkeleton } from '@/components/catalogue/ProductGrid';
import { SortSelect } from '@/components/catalogue/SortSelect';
import { useProducts, type SortKey } from '@/features/catalogue/queries';
import { usePageTitle } from '@/hooks/usePageTitle';
import { t } from '@/i18n';

const PAGE_SIZE = 24;

/**
 * Search results. The URL is the state, and the input is debounced through
 * `useDeferredValue` so typing stays smooth on a budget phone while queries are
 * still cancellable (TanStack Query passes an AbortSignal to every request).
 */
export default function SearchPage() {
  usePageTitle('nav.search');
  const [params, setParams] = useSearchParams();
  const query = params.get('q')?.trim() ?? '';
  const deferredQuery = useDeferredValue(query);
  const sort = (params.get('sort') as SortKey | null) ?? 'popular';
  const page = Math.max(1, Number(params.get('page') ?? '1') || 1);

  const products = useProducts({
    q: deferredQuery,
    sort,
    page,
    pageSize: PAGE_SIZE,
    enabled: deferredQuery.length > 0,
  });

  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== 'page') next.delete('page');
    setParams(next, { replace: key === 'q' });
  };

  if (!query) {
    return (
      <div className="container py-6">
        <h1 className="mb-4 text-xl font-bold">{t('search.startTitle')}</h1>
        <EmptyState icon={SearchIcon} title={t('search.startBody')} />
        <p className="mt-6 text-sm text-muted-foreground">Popular right now</p>
        <ul className="mt-2 flex flex-wrap gap-2">
          {['mustard oil', 'ghee', 'ashwagandha', 'atta', 'toor dal', 'tea'].map((term) => (
            <li key={term}>
              <Link
                to={`/search?q=${encodeURIComponent(term)}`}
                className="inline-flex min-h-touch items-center rounded-full border border-border bg-card px-3 text-sm font-medium hover:border-primary-300"
              >
                {term}
              </Link>
            </li>
          ))}
        </ul>
      </div>
    );
  }

  return (
    <div className="container py-6">
      <h1 className="mb-1 text-xl font-bold">
        Results for <span className="text-primary">“{query}”</span>
      </h1>
      <p className="mb-4 text-sm text-muted-foreground" aria-live="polite">
        {products.data
          ? `${products.data.total} match${products.data.total === 1 ? '' : 'es'}`
          : 'Searching…'}
      </p>

      <div className="mb-4">
        <SortSelect value={sort} onChange={(value) => update('sort', value)} />
      </div>

      {products.isPending ? (
        <ProductGridSkeleton count={8} />
      ) : products.isError ? (
        <EmptyState
          icon={SearchX}
          title="Search is unavailable"
          body="Please check your connection and try again."
          action={<CallStoreButton />}
        />
      ) : products.data && products.data.items.length === 0 ? (
        <EmptyState
          icon={SearchX}
          title={t('search.emptyTitle')}
          body={t('search.emptyBody')}
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
