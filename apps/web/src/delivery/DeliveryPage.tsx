import { MapPin, Phone, RefreshCw, Truck } from 'lucide-react';
import { useState } from 'react';

import { LanguageSelector } from '@/components/common/LanguageSelector';
import { OrderStatusBadge } from '@/components/orders/OrderStatusBadge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/useAuth';
import { useDeliveryAction, useDeliveryOrders } from '@/features/delivery/queries';
import { formatPaise, toTelHref } from '@/lib/utils';

export function DeliveryPage() {
  const { profile, signOut } = useAuth();
  const orders = useDeliveryOrders();
  const action = useDeliveryAction();
  const [actionError, setActionError] = useState<string | null>(null);

  const mark = (orderId: string, next: 'out-for-delivery' | 'delivered') => {
    if (next === 'delivered' && !window.confirm('Confirm this order has been delivered?')) return;
    setActionError(null);
    action.mutate({ orderId, action: next }, { onError: (error) => setActionError(error.message) });
  };

  return (
    <main className="min-h-dvh bg-muted/30">
      <header className="sticky top-0 z-10 border-b border-border bg-background/95 backdrop-blur">
        <div className="mx-auto flex max-w-lg items-center gap-2 px-4 py-3">
          <Truck className="size-5 text-primary" aria-hidden="true" />
          <div className="min-w-0 flex-1">
            <h1 className="truncate text-base font-extrabold">Delivery · MSG Store</h1>
            <p className="truncate text-xs text-muted-foreground">{profile?.name}</p>
          </div>
          <LanguageSelector />
          <Button size="sm" variant="outline" onClick={() => void signOut()}>
            Sign out
          </Button>
        </div>
      </header>

      <section className="mx-auto max-w-lg space-y-3 px-4 py-4 pb-8">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-lg font-bold">My assigned deliveries</h2>
          <Button
            size="sm"
            variant="outline"
            aria-label="Refresh assigned deliveries"
            disabled={orders.isFetching}
            onClick={() => void orders.refetch()}
          >
            <RefreshCw aria-hidden="true" className={orders.isFetching ? 'animate-spin' : ''} />
            Refresh
          </Button>
        </div>

        {orders.isPending && (
          <div role="status" aria-label="Loading assigned deliveries" className="space-y-3">
            <Skeleton className="h-44 w-full rounded-xl" />
            <Skeleton className="h-44 w-full rounded-xl" />
          </div>
        )}
        {orders.isError && (
          <div
            role="alert"
            className="space-y-2 rounded-xl border border-warning/40 bg-warning-soft p-4"
          >
            <p className="text-sm font-medium">Could not load deliveries: {orders.error.message}</p>
            <Button size="sm" variant="outline" onClick={() => void orders.refetch()}>
              Try again
            </Button>
          </div>
        )}
        {actionError && (
          <p role="alert" className="rounded-lg bg-warning-soft p-3 text-sm">
            {actionError}
          </p>
        )}
        {orders.isSuccess && orders.data.items.length === 0 && (
          <div className="rounded-xl border border-dashed border-border bg-background p-6 text-center">
            <Truck className="mx-auto size-8 text-muted-foreground" aria-hidden="true" />
            <p className="mt-2 font-semibold">No active deliveries assigned</p>
            <p className="mt-1 text-sm text-muted-foreground">
              New assigned orders will appear here.
            </p>
          </div>
        )}

        {orders.data?.items.map((order) => {
          const addressText = [
            order.address.line1,
            order.address.line2,
            order.address.landmark,
            order.address.city,
            order.address.state,
            order.address.pincode,
          ]
            .filter(Boolean)
            .join(', ');
          const mapsHref = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(addressText)}`;
          return (
            <article
              key={order.id}
              className="space-y-3 rounded-xl border border-border bg-background p-3 shadow-sm"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="text-sm font-extrabold">{order.order_number}</p>
                  <p className="mt-0.5 text-sm font-semibold">{order.customer_name}</p>
                </div>
                <OrderStatusBadge status={order.status} />
              </div>

              <a
                href={toTelHref(order.customer_phone)}
                className="flex min-h-touch items-center gap-2 rounded-lg border border-border px-3 text-sm font-semibold text-primary"
                aria-label={`Call ${order.customer_name}`}
              >
                <Phone className="size-4" aria-hidden="true" />
                {order.customer_phone || 'No phone number'}
              </a>

              <div className="flex items-start gap-2 text-sm">
                <MapPin className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
                <div className="min-w-0 flex-1">
                  <p className="font-semibold">{order.address.recipient_name}</p>
                  <p className="break-words text-muted-foreground">{addressText}</p>
                  <a
                    href={mapsHref}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-1 inline-block min-h-touch py-2 text-primary underline"
                  >
                    Directions
                  </a>
                </div>
              </div>

              <ul className="divide-y divide-border rounded-lg bg-muted/50 px-3">
                {order.items.map((item, index) => (
                  <li
                    key={`${item.name}-${index}`}
                    className="flex justify-between gap-2 py-2 text-sm"
                  >
                    <span className="min-w-0 break-words">
                      {item.name}{' '}
                      {item.variant_label || item.unit_label
                        ? `· ${item.variant_label || item.unit_label}`
                        : ''}{' '}
                      × {item.quantity}
                    </span>
                    <span className="shrink-0 font-semibold tabular-nums">
                      {formatPaise(item.line_total_paise)}
                    </span>
                  </li>
                ))}
              </ul>

              <div className="flex items-center justify-between gap-2 border-t border-border pt-2 text-sm">
                <span className="text-muted-foreground">
                  {order.payment_method.toUpperCase()} ·{' '}
                  {order.payment_status === 'paid' ? 'Paid' : 'Collect on delivery'}
                </span>
                <span className="font-extrabold tabular-nums">
                  {formatPaise(order.total_paise)}
                </span>
              </div>
              <Button
                className="w-full"
                disabled={action.isPending}
                onClick={() =>
                  mark(order.id, order.status === 'shipped' ? 'out-for-delivery' : 'delivered')
                }
              >
                {action.isPending
                  ? 'Saving…'
                  : order.status === 'shipped'
                    ? 'Mark out for delivery'
                    : 'Mark delivered'}
              </Button>
            </article>
          );
        })}
      </section>
    </main>
  );
}
