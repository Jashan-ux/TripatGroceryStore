import { SlidersHorizontal } from 'lucide-react';

import { SORT_OPTIONS, type SortKey } from '@/features/catalogue/queries';

const SORT_LABELS: Record<SortKey, string> = {
  popular: 'catalogue.sortPopular',
  price_asc: 'catalogue.sortPriceAsc',
  price_desc: 'catalogue.sortPriceDesc',
  rating: 'catalogue.sortTopRated',
  newest: 'catalogue.sortNewest',
  name: 'catalogue.sortName',
};
import { t } from '@/i18n';
import { cn } from '@/lib/utils';

/** Native select on purpose: it is the fastest control on a low-end phone. */
export function SortSelect({
  value,
  onChange,
  className,
}: {
  value: SortKey;
  onChange: (value: SortKey) => void;
  className?: string;
}) {
  return (
    <label className={cn('inline-flex items-center gap-2 text-sm', className)}>
      <SlidersHorizontal className="size-4 text-muted-foreground" aria-hidden="true" />
      <span className="sr-only">{t('catalogue.sortLabel')}</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value as SortKey)}
        className="min-h-touch rounded-lg border border-border bg-background px-2 py-1 text-sm font-medium"
      >
        {SORT_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {t(SORT_LABELS[option.value])}
          </option>
        ))}
      </select>
    </label>
  );
}
