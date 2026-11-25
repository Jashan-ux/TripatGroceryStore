import { CheckCircle2, PackageCheck, XCircle } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { cn, formatIst, formatPaise } from '@/lib/utils';
import { usePageTitle } from '@/hooks/usePageTitle';
import type { AdminReturnOut } from '@tripat/api-client';
import {
  useAdminReturns,
  useDecideReturn,
  useReceiveReturn,
  type AdminReturnFilter,
} from '@/admin/adminReturns';

const TABS: { value: AdminReturnFilter; label: string }[] = [
  { value: 'requested', label: 'Waiting' },
  { value: 'approved', label: 'Approved' },
  { value: 'received_credited', label: 'Credited' },
  { value: 'rejected', label: 'Refused' },
  { value: 'all', label: 'All' },
];

const STATUS_LABEL: Record<string, string> = {
  requested: 'Waiting for a decision',
  approved: 'Approved · goods not back yet',
  rejected: 'Refused',
  received_credited: 'Credited to wallet',
};

/**
 * The return queue.
 *
 * Two separate taps on purpose — approve, then "goods received" — because the
 * customer is only paid on the second one. The server refuses to credit twice and
 * refuses to credit a return that was never approved; this page just shows which
 * of the two is next.
 */
export function AdminReturnsPage() {
  usePageTitle(undefined, 'Returns · Admin');
  const [status, setStatus] = useState<AdminReturnFilter>('requested');
  const [page, setPage] = useState(1);
  const [note, setNote] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);

  const returns = useAdminReturns({ status, page });
  const decide = useDecideReturn();
  const receive = useReceiveReturn();
  const data = returns.data;

  const act = (kind: 'approve' | 'refuse' | 'receive', item: AdminReturnOut) => {
    setError(null);
    const noteText = note[item.id] ?? '';
    const onError = (err: Error) => setError(err.message);
    if (kind === 'receive') {
      receive.mutate({ returnId: item.id, note: noteText }, { onError });
      return;
    }
    decide.mutate({ returnId: item.id, approve: kind === 'approve', note: noteText }, { onError });
  };

  return (
    <div className="container max-w-4xl space-y-4 py-5 pb-nav-safe md:pb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-extrabold tracking-tight">Returns</h1>
        <p className="text-xs text-muted-foreground">
          {data ? `${data.total} return${data.total === 1 ? '' : 's'}` : 'Loading…'}
        </p>
      </div>

      <p className="rounded-lg bg-muted/60 p-2.5 text-xs text-muted-foreground">
        Approve first, then mark received when the goods are back — the wallet is credited only on
        that second step, and only once.
      </p>

      <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Return status">
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

      {error && (
        <p
          role="alert"
          className="rounded-lg border border-border bg-warning-soft p-2.5 text-sm font-medium text-warning"
        >
          {error}
        </p>
      )}

      {returns.isPending ? (
        <div className="space-y-2">
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-24 w-full rounded-xl" />
        </div>
      ) : !data || data.items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
          Nothing here. Returns you approve or refuse move to their own tabs.
        </p>
      ) : (
        <ul className="space-y-2">
          {data.items.map((item) => (
            <ReturnCard
              key={item.id}
              item={item}
              note={note[item.id] ?? ''}
              onNote={(value) => setNote((prev) => ({ ...prev, [item.id]: value }))}
              busy={
                (decide.isPending && decide.variables?.returnId === item.id) ||
                (receive.isPending && receive.variables?.returnId === item.id)
              }
              onAct={(kind) => act(kind, item)}
            />
          ))}
        </ul>
      )}

      {data && data.total_pages > 1 && (
        <div className="flex items-center justify-between text-sm">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((value) => value - 1)}
          >
            Previous
          </Button>
          <span className="text-muted-foreground">
            Page {data.page} of {data.total_pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= data.total_pages}
            onClick={() => setPage((value) => value + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  );
}

function ReturnCard({
  item,
  note,
  onNote,
  busy,
  onAct,
}: {
  item: AdminReturnOut;
  note: string;
  onNote: (value: string) => void;
  busy: boolean;
  onAct: (kind: 'approve' | 'refuse' | 'receive') => void;
}) {
  return (
    <li className="rounded-xl border border-border bg-card p-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-bold">
            {item.order_number} · {item.customer_name || 'Customer'}
          </p>
          <p className="text-xs text-muted-foreground">
            {item.customer_phone || 'no phone'} · asked{' '}
            {formatIst(item.requested_at, { day: 'numeric', month: 'short', hour: 'numeric' })}
          </p>
        </div>
        <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-semibold">
          {STATUS_LABEL[item.status] ?? item.status}
        </span>
      </div>

      <ul className="mt-2 space-y-0.5 text-sm">
        {item.items.map((line) => (
          <li key={line.order_item_id} className="flex justify-between gap-2">
            <span>
              {line.name} × {line.quantity}
            </span>
            <span className="tabular-nums text-muted-foreground">
              {formatPaise(line.refund_paise)}
            </span>
          </li>
        ))}
      </ul>
      {item.reason && <p className="mt-1 rounded-lg bg-muted/60 p-2 text-xs">“{item.reason}”</p>}
      <p className="mt-1 text-sm font-semibold">
        Refund {formatPaise(item.refund_paise)} to wallet
      </p>

      {item.status !== 'received_credited' && item.status !== 'rejected' && (
        <>
          <input
            aria-label={`Note for ${item.order_number}`}
            value={note}
            maxLength={300}
            onChange={(event) => onNote(event.target.value)}
            placeholder="Note (optional)"
            className="mt-2 w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
          />
          <div className="mt-2 flex flex-wrap gap-2">
            {item.status === 'requested' && (
              <>
                <Button size="sm" disabled={busy} onClick={() => onAct('approve')}>
                  <CheckCircle2 aria-hidden="true" />
                  Approve
                </Button>
                <Button variant="outline" size="sm" disabled={busy} onClick={() => onAct('refuse')}>
                  <XCircle aria-hidden="true" />
                  Refuse
                </Button>
              </>
            )}
            {item.status === 'approved' && (
              <Button size="sm" disabled={busy} onClick={() => onAct('receive')}>
                <PackageCheck aria-hidden="true" />
                {busy ? 'Crediting…' : 'Goods received · credit wallet'}
              </Button>
            )}
          </div>
        </>
      )}
      {item.status === 'received_credited' && item.received_at && (
        <p className="mt-1 text-xs text-muted-foreground">
          Credited {formatIst(item.received_at, { day: 'numeric', month: 'short' })} ·{' '}
          {formatPaise(item.refund_paise)}
        </p>
      )}
      {item.decision_note && (
        <p className="mt-1 text-xs text-muted-foreground">Note: “{item.decision_note}”</p>
      )}
    </li>
  );
}
