import { ChevronRight, ReceiptText } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { ProductThumb } from '@/components/catalogue/ProductCard';
import { EmptyState } from '@/components/common/EmptyState';
import { OrderStatusBadge } from '@/components/orders/OrderStatusBadge';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useOrders } from '@/features/orders/queries';
import { usePageTitle } from '@/hooks/usePageTitle';
import { formatIst, formatPaise } from '@/lib/utils';

/** Everything the shopper ordered, newest first. */
export default function OrdersPage() {
  usePageTitle(undefined, 'Your orders');
  const [page, setPage] = useState(1);
  const orders = useOrders(page);

  const data = orders.data;

  return (
    <div className="container max-w-3xl py-6 pb-nav-safe md:pb-8">
      <h1 className="mb-4 text-xl font-extrabold tracking-tight">Your orders</h1>

      {orders.isPending ? (
        <div className="space-y-3" role="status" aria-live="polite">
          <span className="sr-only">Loading your orders</span>
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-24 w-full rounded-xl" />
          ))}
        </div>
      ) : orders.isError ? (
        <EmptyState
          icon={ReceiptText}
          title="We could not load your orders"
          body="Check your connection and try again — your orders are safe."
          action={
            <Button className="mt-2" onClick={() => void orders.refetch()}>
              Try again
            </Button>
          }
        />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={ReceiptText}
          title="No orders yet"
          body="When you order groceries they will appear here, with live status and a way to call it off."
          action={
            <Button asChild className="mt-2">
              <Link to="/categories">Start shopping</Link>
            </Button>
          }
        />
      ) : (
        <>
          <ul className="space-y-3">
            {data.items.map((order) => (
              <li key={order.id}>
                <Link
                  to={`/orders/${order.id}`}
                  className="flex items-center gap-3 rounded-xl border border-border bg-card p-3 transition-shadow hover:shadow-elev1"
                >
                  <div className="size-14 shrink-0 overflow-hidden rounded-lg bg-secondary">
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
                    </div>
                    <p className="truncate text-sm text-muted-foreground">
                      {order.item_count} item{order.item_count === 1 ? '' : 's'}
                      {order.first_item_name ? ` · ${order.first_item_name}` : ''}
                    </p>
                    <p className="text-xs text-muted-foreground">
                      {formatIst(order.placed_at)} · {formatPaise(order.total_paise)}
                    </p>
                  </div>
                  <ChevronRight
                    className="size-4 shrink-0 text-muted-foreground"
                    aria-hidden="true"
                  />
                </Link>
              </li>
            ))}
          </ul>

          {data.total_pages > 1 && (
            <nav className="mt-4 flex items-center justify-between gap-3" aria-label="Order pages">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                Newer
              </Button>
              <span className="text-xs text-muted-foreground">
                Page {data.page} of {data.total_pages} · {data.total} order
                {data.total === 1 ? '' : 's'}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= data.total_pages}
                onClick={() => setPage((current) => current + 1)}
              >
                Older
              </Button>
            </nav>
          )}
        </>
      )}
    </div>
  );
}
