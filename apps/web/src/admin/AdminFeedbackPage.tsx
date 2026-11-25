import { Check, MailCheck } from 'lucide-react';
import { useState } from 'react';

import { useAdminFeedback, useMarkFeedbackRead } from '@/admin/adminCatalogue';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { usePageTitle } from '@/hooks/usePageTitle';
import { cn, formatIst } from '@/lib/utils';

const TABS: { value: 'new' | 'read' | 'all'; label: string }[] = [
  { value: 'new', label: 'New' },
  { value: 'read', label: 'Read' },
  { value: 'all', label: 'All' },
];

const KIND_LABEL: Record<string, string> = {
  general: 'Question',
  order: 'Order',
  product: 'Product',
  other: 'Other',
};

/**
 * The feedback inbox.
 *
 * Messages arrive here the moment the contact form is submitted — the email is a
 * convenience, not the record. "Read" is a deliberate tap, because an inbox that
 * marks everything read on open is an inbox nobody trusts.
 */
export function AdminFeedbackPage() {
  usePageTitle(undefined, 'Inbox · Admin');
  const [status, setStatus] = useState<'new' | 'read' | 'all'>('new');
  const [page, setPage] = useState(1);
  const feedback = useAdminFeedback(status, page);
  const markRead = useMarkFeedbackRead();
  const data = feedback.data;

  return (
    <div className="container max-w-3xl space-y-4 py-5 pb-nav-safe md:pb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-extrabold tracking-tight">Inbox</h1>
        <p className="text-xs text-muted-foreground">
          {data ? `${data.total} message${data.total === 1 ? '' : 's'}` : 'Loading…'}
        </p>
      </div>

      <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Message status">
        {TABS.map((tab) => (
          <button
            key={tab.value}
            type="button"
            role="tab"
            aria-selected={status === tab.value}
            onClick={() => {
              setStatus(tab.value);
              setPage(1);
            }}
            className={cn(
              'min-h-touch rounded-full px-3 text-sm font-semibold transition-colors',
              status === tab.value
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-muted/70',
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {markRead.isError && (
        <p role="alert" className="rounded-lg bg-warning-soft p-2.5 text-sm text-warning">
          {markRead.error.message}
        </p>
      )}

      {feedback.isPending ? (
        <Skeleton className="h-48 w-full rounded-xl" />
      ) : !data || data.items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
          {status === 'new'
            ? 'No unread messages. Nice.'
            : 'Nothing in this tab yet. Messages from the contact page land here.'}
        </p>
      ) : (
        <ul className="space-y-2">
          {data.items.map((item) => (
            <li key={item.id} className="rounded-xl border border-border bg-card p-3">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-bold">{item.name || 'A customer'}</p>
                <Badge tone="neutral">{KIND_LABEL[item.kind] ?? item.kind}</Badge>
                {item.status === 'new' && <Badge tone="brand">New</Badge>}
                <p className="ml-auto text-xs text-muted-foreground">
                  {formatIst(item.created_at, {
                    day: 'numeric',
                    month: 'short',
                    hour: '2-digit',
                    minute: '2-digit',
                  })}
                </p>
              </div>
              <p className="mt-1.5 whitespace-pre-line text-sm">{item.message}</p>
              <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
                {item.phone && (
                  <a href={`tel:${item.phone}`} className="font-semibold text-primary">
                    {item.phone}
                  </a>
                )}
                {item.email && (
                  <a href={`mailto:${item.email}`} className="font-semibold text-primary">
                    {item.email}
                  </a>
                )}
                {item.status === 'new' ? (
                  <Button
                    size="sm"
                    variant="outline"
                    className="ml-auto"
                    disabled={markRead.isPending}
                    onClick={() => markRead.mutate(item.id)}
                  >
                    <Check aria-hidden="true" /> Mark read
                  </Button>
                ) : (
                  <span className="ml-auto inline-flex items-center gap-1 text-muted-foreground">
                    <MailCheck className="size-3.5" aria-hidden="true" />
                    {item.read_at ? `Read ${formatIst(item.read_at)}` : 'Read'}
                  </span>
                )}
              </div>
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
