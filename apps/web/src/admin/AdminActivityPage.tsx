import { History } from 'lucide-react';
import { useState } from 'react';

import { useAdminAudit } from '@/admin/adminCatalogue';
import { Button } from '@/components/ui/button';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { usePageTitle } from '@/hooks/usePageTitle';
import { formatIst } from '@/lib/utils';

/** Audit values are JSON scalars; anything else is shown as JSON, never as `[object Object]`. */
function renderValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  return JSON.stringify(value) ?? '';
}

const ENTITY_LABEL: Record<string, string> = {
  product: 'Product',
  category: 'Category',
  brand: 'Brand',
  settings: 'Settings',
  offer: 'Offer',
  feedback: 'Inbox',
  order: 'Order',
  return: 'Return',
};

/**
 * Activity: who changed what, and what it was before.
 *
 * This is the answer to "who lowered the price of ghee?" — the row keeps the
 * before and after values, so the question never needs a support ticket.
 */
export function AdminActivityPage() {
  usePageTitle(undefined, 'Activity · Admin');
  const [entity, setEntity] = useState('');
  const [page, setPage] = useState(1);
  const log = useAdminAudit(entity, page);
  const data = log.data;

  return (
    <div className="container max-w-3xl space-y-4 py-5 pb-nav-safe md:pb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="flex items-center gap-2 text-xl font-extrabold tracking-tight">
          <History className="size-5" aria-hidden="true" /> Activity
        </h1>
        <p className="text-xs text-muted-foreground">
          {data ? `${data.total} change${data.total === 1 ? '' : 's'}` : 'Loading…'}
        </p>
      </div>

      <label className="block max-w-56 text-xs font-semibold">
        Show
        <Select
          className="mt-1"
          value={entity}
          onChange={(event) => {
            setEntity(event.target.value);
            setPage(1);
          }}
        >
          <option value="">Everything</option>
          {Object.entries(ENTITY_LABEL).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </Select>
      </label>

      {log.isPending ? (
        <Skeleton className="h-48 w-full rounded-xl" />
      ) : !data || data.items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
          Nothing recorded yet. Price changes, settings edits and offers all appear here.
        </p>
      ) : (
        <ul className="space-y-2">
          {data.items.map((entry) => (
            <li key={entry.id} className="rounded-xl border border-border bg-card p-3">
              <div className="flex flex-wrap items-baseline gap-2">
                <p className="text-sm font-bold">{entry.action}</p>
                <p className="text-xs text-muted-foreground">
                  {ENTITY_LABEL[entry.entity] ?? entry.entity}
                  {entry.summary ? ` · ${entry.summary}` : ''}
                </p>
                <p className="ml-auto text-xs text-muted-foreground">
                  {formatIst(entry.created_at, {
                    day: 'numeric',
                    month: 'short',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </p>
              </div>
              <p className="mt-0.5 text-xs text-muted-foreground">{entry.actor_email}</p>
              {Object.keys(entry.after ?? {}).length > 0 && (
                <dl className="mt-1.5 grid grid-cols-1 gap-x-4 text-xs sm:grid-cols-2">
                  {Object.entries(entry.after ?? {}).map(([field, value]) => (
                    <div key={field} className="flex gap-1.5">
                      <dt className="font-semibold">{field}:</dt>
                      <dd className="text-muted-foreground">
                        {renderValue(entry.before?.[field])} → {renderValue(value)}
                      </dd>
                    </div>
                  ))}
                </dl>
              )}
              {entry.note && (
                <p className="mt-1 text-xs italic text-muted-foreground">{entry.note}</p>
              )}
            </li>
          ))}
        </ul>
      )}

      {data && data.total_pages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <p className="text-xs text-muted-foreground">
            Page {data.page} of {data.total_pages}
          </p>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= data.total_pages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}
