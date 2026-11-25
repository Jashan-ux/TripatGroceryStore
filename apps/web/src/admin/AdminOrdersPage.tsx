import { ChevronDown, MapPin, Phone, Search, Truck } from 'lucide-react';
import { useEffect, useState } from 'react';

import { ProductThumb } from '@/components/catalogue/ProductCard';
import { OrderStatusBadge } from '@/components/orders/OrderStatusBadge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { usePageTitle } from '@/hooks/usePageTitle';
import { cn, formatIst, formatPaise, toTelHref } from '@/lib/utils';
import type { AdminOrderStatusIn, AdminOrderSummaryOut, OrderOut } from '@tripat/api-client';
import {
  ADMIN_PAGE_SIZE,
  nextStep,
  useAdminOrder,
  useAdminOrders,
  useSetOrderStatus,
  type AdminStatusFilter,
} from '@/admin/adminOrders';

const TABS: { value: AdminStatusFilter; label: string; countKey: string | null }[] = [
  { value: 'all', label: 'All', countKey: null },
  { value: 'processing', label: 'New', countKey: 'processing' },
  { value: 'shipped', label: 'Shipped', countKey: 'shipped' },
  { value: 'out_for_delivery', label: 'Out', countKey: 'out_for_delivery' },
  { value: 'delivered', label: 'Delivered', countKey: 'delivered' },
  { value: 'cancelled', label: 'Cancelled', countKey: 'cancelled' },
];

/**
 * The shop's order queue.
 *
 * Built for the counter phone: one row per order, the next step as a single tap,
 * and the phone number as a call link. Stock and payment side effects happen in
 * the API (a cancel restores stock, a delivery settles the cash), so this page
 * never computes money or stock itself.
 */
export function AdminOrdersPage() {
  usePageTitle(undefined, 'Orders · Admin');
  const [status, setStatus] = useState<AdminStatusFilter>('processing');
  const [term, setTerm] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string | null>(null);

  // Debounce the search box; the query string is what actually hits the API.
  useEffect(() => {
    const timer = setTimeout(() => setQuery(term), 300);
    return () => clearTimeout(timer);
  }, [term]);

  const orders = useAdminOrders({ status, q: query, page });
  const data = orders.data;

  return (
    <div className="container max-w-4xl space-y-4 py-5 pb-nav-safe md:pb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-extrabold tracking-tight">Orders</h1>
        <p className="text-xs text-muted-foreground">
          {data ? `${data.total} order${data.total === 1 ? '' : 's'}` : 'Loading…'}
        </p>
      </div>

      <div className="flex flex-wrap gap-1.5" role="tablist" aria-label="Order status">
        {TABS.map((tab) => {
          const count = tab.countKey ? data?.counts[tab.countKey] : undefined;
          const active = status === tab.value;
          return (
            <button
              key={tab.value}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => {
                setStatus(tab.value);
                setPage(1);
              }}
              className={cn(
                'min-h-touch rounded-full px-3 text-sm font-semibold transition-colors',
                active
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-foreground hover:bg-muted',
              )}
            >
              {tab.label}
              {typeof count === 'number' && count > 0 && (
                <span
                  className={cn(
                    'ml-1.5 text-xs',
                    active ? 'text-primary-foreground/80' : 'text-muted-foreground',
                  )}
                >
                  {count}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div className="relative">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <Input
          aria-label="Search orders"
          placeholder="Order number, customer name or phone"
          value={term}
          onChange={(event) => {
            setTerm(event.target.value);
            setPage(1);
          }}
          className="pl-9"
        />
      </div>

      {orders.isPending ? (
        <div className="space-y-2" role="status" aria-live="polite">
          <span className="sr-only">Loading orders</span>
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-24 w-full rounded-xl" />
          ))}
        </div>
      ) : orders.isError ? (
        <div className="rounded-xl border border-border bg-card p-4 text-sm" role="alert">
          <p className="font-semibold">Could not load the queue</p>
          <p className="text-muted-foreground">{orders.error.message}</p>
          <Button
            size="sm"
            variant="outline"
            className="mt-2"
            onClick={() => void orders.refetch()}
          >
            Try again
          </Button>
        </div>
      ) : !data || data.items.length === 0 ? (
        <p className="rounded-xl border border-border bg-card p-6 text-center text-sm text-muted-foreground">
          Nothing here right now. New orders appear on their own — pull to refresh if you are
          impatient.
        </p>
      ) : (
        <ul className="space-y-2">
          {data.items.map((order) => (
            <li key={order.id}>
              <OrderRow
                order={order}
                expanded={expanded === order.id}
                onToggle={() => setExpanded((current) => (current === order.id ? null : order.id))}
              />
            </li>
          ))}
        </ul>
      )}

      {data && data.total_pages > 1 && (
        <nav className="flex items-center justify-between gap-3" aria-label="Order pages">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Newer
          </Button>
          <span className="text-xs text-muted-foreground">
            Page {data.page} of {data.total_pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= data.total_pages}
            onClick={() => setPage((p) => p + 1)}
          >
            Older
          </Button>
        </nav>
      )}
      <p className="text-center text-[11px] text-muted-foreground">
        Showing up to {ADMIN_PAGE_SIZE} orders per page · status labels match what the customer
        sees.
      </p>
    </div>
  );
}

function OrderRow({
  order,
  expanded,
  onToggle,
}: {
  order: AdminOrderSummaryOut;
  expanded: boolean;
  onToggle: () => void;
}) {
  const setStatus = useSetOrderStatus();
  const next = nextStep(order.status);
  const [note, setNote] = useState('');
  const [error, setError] = useState<string | null>(null);

  const move = (target: AdminOrderStatusIn['status'], text = '') => {
    setError(null);
    setStatus.mutate(
      { orderId: order.id, status: target, note: text },
      { onError: (err) => setError(err.message) },
    );
  };

  return (
    <article className="rounded-xl border border-border bg-card">
      <div className="flex flex-wrap items-center gap-3 p-3">
        <div className="size-11 shrink-0 overflow-hidden rounded-lg bg-secondary">
          <ProductThumb
            name={order.first_item_name || 'Order'}
            imageUrl={order.first_item_image_url || null}
            size="sm"
          />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm font-bold">{order.order_number}</span>
            <OrderStatusBadge status={order.status} />
            {order.is_new && (
              <span className="rounded-full bg-primary-50 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-primary-800">
                New
              </span>
            )}
          </div>
          <p className="truncate text-xs text-muted-foreground">
            {order.customer_name || 'Customer'} · {order.item_count} item
            {order.item_count === 1 ? '' : 's'} ·{' '}
            {formatIst(order.placed_at, {
              day: 'numeric',
              month: 'short',
              hour: 'numeric',
              minute: '2-digit',
            })}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-2">
          <span className="text-sm font-extrabold tabular-nums">
            {formatPaise(order.total_paise)}
          </span>
          <a
            href={toTelHref(order.customer_phone)}
            className="inline-flex size-9 items-center justify-center rounded-lg border border-border text-primary hover:bg-secondary"
            aria-label={`Call ${order.customer_name || 'customer'}`}
          >
            <Phone className="size-4" aria-hidden="true" />
          </a>
          <button
            type="button"
            onClick={onToggle}
            aria-expanded={expanded}
            className="inline-flex size-9 items-center justify-center rounded-lg border border-border hover:bg-secondary"
            aria-label={
              expanded
                ? `Hide details for ${order.order_number}`
                : `Show details for ${order.order_number}`
            }
          >
            <ChevronDown
              className={cn('size-4 transition-transform', expanded && 'rotate-180')}
              aria-hidden="true"
            />
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2 border-t border-border p-3">
        {next && (
          <Button size="sm" disabled={setStatus.isPending} onClick={() => move(next.status)}>
            <Truck aria-hidden="true" />
            {next.label}
          </Button>
        )}
        {order.status === 'processing' && (
          <Button
            size="sm"
            variant="outline"
            disabled={setStatus.isPending}
            onClick={() => move('cancelled', 'Cancelled from the shop')}
          >
            Cancel order
          </Button>
        )}
        {order.payment_status === 'pending' && order.status !== 'cancelled' && (
          <span className="self-center text-xs text-muted-foreground">
            Collect {formatPaise(order.total_paise)} in cash
          </span>
        )}
        {setStatus.isPending && (
          <span className="self-center text-xs text-muted-foreground">Saving…</span>
        )}
        {error && (
          <p role="alert" className="w-full text-xs font-medium text-primary-700">
            {error}
          </p>
        )}
      </div>

      {expanded && (
        <OrderDetailPanel
          orderId={order.id}
          note={note}
          onNoteChange={setNote}
          onCancel={() => move('cancelled', note)}
          cancelling={setStatus.isPending}
        />
      )}
    </article>
  );
}

function OrderDetailPanel({
  orderId,
  note,
  onNoteChange,
  onCancel,
  cancelling,
}: {
  orderId: string;
  note: string;
  onNoteChange: (value: string) => void;
  onCancel: () => void;
  cancelling: boolean;
}) {
  const detail = useAdminOrder(orderId);

  if (detail.isPending) return <Skeleton className="m-3 h-32 rounded-lg" />;
  if (detail.isError || !detail.data) {
    return <p className="m-3 text-sm text-muted-foreground">Could not load this order.</p>;
  }

  return (
    <Details
      order={detail.data}
      note={note}
      onNoteChange={onNoteChange}
      onCancel={onCancel}
      cancelling={cancelling}
    />
  );
}

function Details({
  order,
  note,
  onNoteChange,
  onCancel,
  cancelling,
}: {
  order: OrderOut;
  note: string;
  onNoteChange: (value: string) => void;
  onCancel: () => void;
  cancelling: boolean;
}) {
  return (
    <div className="space-y-4 border-t border-border p-3 text-sm">
      <ul className="divide-y divide-border">
        {order.items.map((item) => (
          <li key={item.id} className="flex items-center justify-between gap-3 py-1.5">
            <span className="min-w-0">
              <span className="block truncate font-medium">{item.name}</span>
              <span className="text-xs text-muted-foreground">
                {[item.variant_label, item.unit_label].filter(Boolean).join(' · ')} ×{' '}
                {item.quantity}
              </span>
            </span>
            <span className="font-semibold tabular-nums">{formatPaise(item.line_total_paise)}</span>
          </li>
        ))}
      </ul>

      <div className="flex items-start gap-2 rounded-lg bg-muted/60 p-2.5 text-xs">
        <MapPin className="mt-0.5 size-3.5 shrink-0 text-primary" aria-hidden="true" />
        <span>
          <span className="block font-semibold">{order.address.recipient_name}</span>
          {[
            [order.address.line1, order.address.line2].filter(Boolean).join(', '),
            order.address.landmark,
            order.address.city,
            order.address.pincode,
          ]
            .filter(Boolean)
            .join(', ')}
          {order.customer_note && (
            <span className="mt-1 block italic">“{order.customer_note}”</span>
          )}
        </span>
      </div>

      <div className="text-xs text-muted-foreground">
        <p>
          Placed{' '}
          {formatIst(order.placed_at, {
            day: 'numeric',
            month: 'short',
            hour: 'numeric',
            minute: '2-digit',
          })}{' '}
          · cash on delivery · {order.payment_status === 'paid' ? 'paid' : 'unpaid'}
        </p>
        <ol className="mt-2 space-y-1">
          {order.events.map((event, index) => (
            <li key={`${event.created_at}-${index}`}>
              <span className="font-semibold capitalize text-foreground">
                {event.status.replace(/_/g, ' ')}
              </span>{' '}
              {formatIst(event.created_at, {
                day: 'numeric',
                month: 'short',
                hour: 'numeric',
                minute: '2-digit',
              })}{' '}
              · {event.actor}
              {event.note ? ` · ${event.note}` : ''}
            </li>
          ))}
        </ol>
      </div>

      {order.status === 'processing' && (
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex-1">
            <label htmlFor="cancel-reason" className="mb-1 block text-xs font-semibold">
              Reason (saved with the cancellation)
            </label>
            <Input
              id="cancel-reason"
              value={note}
              maxLength={300}
              onChange={(event) => onNoteChange(event.target.value)}
              placeholder="Customer asked to skip the order"
            />
          </div>
          <Button variant="destructive" size="sm" onClick={onCancel} disabled={cancelling}>
            Cancel & restore stock
          </Button>
        </div>
      )}
    </div>
  );
}
