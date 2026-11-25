import { SlidersHorizontal } from 'lucide-react';

import { SORT_OPTIONS, type SortKey } from '@/features/catalogue/queries';
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
      <span className="sr-only">Sort products</span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value as SortKey)}
        className="min-h-touch rounded-lg border border-border bg-background px-2 py-1 text-sm font-medium"
      >
        {SORT_OPTIONS.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </label>
  );
}
