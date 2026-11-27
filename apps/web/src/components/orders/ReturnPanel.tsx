import { PackageX } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { useRequestReturn, useReturns } from '@/features/rewards/queries';
import type { OrderOut } from '@tripat/api-client';
import { cn, formatPaise } from '@/lib/utils';

const STATUS_COPY: Record<string, string> = {
  requested: 'Waiting for the store to review it',
  approved: 'Approved — we are waiting for the items',
  rejected: 'Not approved',
  received_credited: 'Received — money is in your wallet',
};

const MAX_REASON = 200;

/**
 * Returning part of a delivered order.
 *
 * The money-back promise is the API's, not this component's: nothing is credited
 * until the shop approves *and* receives the items, so the copy says exactly that
 * instead of "refund issued" the moment the button is pressed.
 */
export function ReturnPanel({ order }: { order: OrderOut }) {
  const returns = useReturns();
  const request = useRequestReturn();
  const [open, setOpen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  // Quantities are keyed by order item id; 0 means "not returning this line".
  const [quantities, setQuantities] = useState<Record<string, number>>({});

  const mine = (returns.data?.returns ?? []).filter((entry) => entry.order_id === order.id);
  const openRequest = mine.some(
    (entry) => entry.status === 'requested' || entry.status === 'approved',
  );

  if (order.status !== 'delivered') {
    // Before delivery the right verb is "cancel"; after, "return".
    return null;
  }

  const chosen = Object.entries(quantities).filter(([, quantity]) => quantity > 0);
  const refundPreview = chosen.reduce((sum, [id, quantity]) => {
    const line = order.items.find((item) => item.id === id);
    if (!line) return sum;
    const unit = Math.round(line.line_total_paise / Math.max(line.quantity, 1));
    return sum + unit * quantity;
  }, 0);

  const submit = () => {
    setError(null);
    request.mutate(
      {
        orderId: order.id,
        items: chosen.map(([order_item_id, quantity]) => ({ order_item_id, quantity })),
        reason: reason.trim(),
      },
      {
        onSuccess: () => {
          setOpen(false);
          setReason('');
          setQuantities({});
        },
        onError: (err) => setError(err.message),
      },
    );
  };

  return (
    <section
      aria-labelledby="return-heading"
      className="rounded-xl border border-border bg-card p-4 text-sm"
    >
      <h2 id="return-heading" className="mb-1 flex items-center gap-2 font-bold">
        <PackageX className="size-4 text-primary" aria-hidden="true" />
        Returns
      </h2>

      {mine.length > 0 && (
        <ul className="mb-2 space-y-1.5">
          {mine.map((entry) => (
            <li key={entry.id} className="rounded-lg bg-muted/60 p-2">
              <p className="font-semibold">{STATUS_COPY[entry.status] ?? entry.status}</p>
              <p className="text-xs text-muted-foreground">
                {entry.items.map((item) => `${item.name} ×${item.quantity}`).join(', ')} ·{' '}
                {formatPaise(entry.refund_paise)}
              </p>
              {entry.decision_note && (
                <p className="text-xs text-muted-foreground">“{entry.decision_note}”</p>
              )}
            </li>
          ))}
        </ul>
      )}

      {openRequest ? (
        <p className="text-xs text-muted-foreground">
          This order already has a return in progress. We will notify you when it moves.
        </p>
      ) : !open ? (
        <Button variant="outline" size="sm" className="w-full" onClick={() => setOpen(true)}>
          Return an item
        </Button>
      ) : (
        <div className="space-y-2">
          <p className="text-xs text-muted-foreground">
            Pick what to send back. Money reaches your wallet once we approve the return and the
            items are back with us.
          </p>
          <ul className="space-y-2">
            {order.items.map((item) => {
              const quantity = quantities[item.id] ?? 0;
              return (
                <li key={item.id} className="flex items-center justify-between gap-2">
                  <span className="min-w-0">
                    <span className="block truncate text-sm font-medium">{item.name}</span>
                    <span className="block text-xs text-muted-foreground">
                      Bought {item.quantity} · {formatPaise(item.line_total_paise)}
                    </span>
                  </span>
                  <div className="flex shrink-0 items-center gap-1">
                    <Button
                      variant="outline"
                      size="icon"
                      aria-label={`Fewer ${item.name}`}
                      disabled={quantity === 0}
                      onClick={() =>
                        setQuantities((prev) => ({ ...prev, [item.id]: quantity - 1 }))
                      }
                    >
                      −
                    </Button>
                    <span className="w-6 text-center tabular-nums">{quantity}</span>
                    <Button
                      variant="outline"
                      size="icon"
                      aria-label={`More ${item.name}`}
                      disabled={quantity >= item.quantity}
                      onClick={() =>
                        setQuantities((prev) => ({ ...prev, [item.id]: quantity + 1 }))
                      }
                    >
                      +
                    </Button>
                  </div>
                </li>
              );
            })}
          </ul>
          <label htmlFor="return-reason" className="block text-xs font-semibold">
            What went wrong?
          </label>
          <textarea
            id="return-reason"
            value={reason}
            maxLength={MAX_REASON}
            rows={2}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Damaged on arrival, wrong item…"
            className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
          />
          {error && (
            <p role="alert" className="text-xs font-medium text-primary-700">
              {error}
            </p>
          )}
          <p className={cn('text-xs', chosen.length === 0 && 'text-muted-foreground')}>
            Up to {formatPaise(refundPreview)} back to your wallet.
          </p>
          <div className="flex gap-2">
            <Button
              size="sm"
              className="flex-1"
              disabled={chosen.length === 0 || request.isPending}
              onClick={submit}
            >
              {request.isPending ? 'Sending…' : 'Request return'}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setOpen(false);
                setError(null);
              }}
            >
              Not now
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}
