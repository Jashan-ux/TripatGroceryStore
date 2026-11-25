import { SearchX, Search as SearchIcon } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';

import { CallStoreButton } from '@/components/common/CallStoreButton';
import { EmptyState } from '@/components/common/EmptyState';
import { usePageTitle } from '@/hooks/usePageTitle';
import { t } from '@/i18n';

/**
 * Search results. The query string is the source of truth (shareable URLs,
 * back/forward works). Results arrive with the catalogue phase; the empty and
 * zero-result states are already final copy.
 */
export default function SearchPage() {
  usePageTitle('nav.search');
  const [params] = useSearchParams();
  const query = params.get('q')?.trim() ?? '';

  if (!query) {
    return (
      <div className="container py-6">
        <h1 className="mb-4 text-xl font-bold">{t('search.startTitle')}</h1>
        <EmptyState icon={SearchIcon} title={t('search.startBody')} />
      </div>
    );
  }

  return (
    <div className="container py-6">
      <h1 className="mb-1 text-xl font-bold">
        Results for <span className="text-primary">“{query}”</span>
      </h1>
      <p className="mb-4 text-sm text-muted-foreground">
        Showing matches for your search. Filters and sorting arrive with the catalogue.
      </p>
      <EmptyState
        icon={SearchX}
        title={t('search.emptyTitle')}
        body={t('search.emptyBody')}
        action={<CallStoreButton />}
      />
    </div>
  );
}
