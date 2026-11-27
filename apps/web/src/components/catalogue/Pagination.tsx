import { ChevronLeft, ChevronRight } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { t } from '@/i18n';

export function Pagination({
  page,
  totalPages,
  onChange,
}: {
  page: number;
  totalPages: number;
  onChange: (page: number) => void;
}) {
  if (totalPages <= 1) return null;
  return (
    <nav
      aria-label={t('catalogue.pagination')}
      className="mt-6 flex items-center justify-center gap-3"
    >
      <Button
        variant="outline"
        size="sm"
        onClick={() => onChange(page - 1)}
        disabled={page <= 1}
        aria-label={`${t('catalogue.previous')} ${t('catalogue.page')}`}
      >
        <ChevronLeft className="size-4" aria-hidden="true" />
        {t('catalogue.previous')}
      </Button>
      <p className="text-sm text-muted-foreground" aria-live="polite">
        {t('catalogue.page')} {page} {t('catalogue.of')} {totalPages}
      </p>
      <Button
        variant="outline"
        size="sm"
        onClick={() => onChange(page + 1)}
        disabled={page >= totalPages}
        aria-label={`${t('catalogue.next')} ${t('catalogue.page')}`}
      >
        {t('catalogue.next')}
        <ChevronRight className="size-4" aria-hidden="true" />
      </Button>
    </nav>
  );
}
