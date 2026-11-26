import { ArrowLeft, MapPin, Star } from 'lucide-react';
import { Link, useParams } from 'react-router-dom';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import { useCustomerProfile } from '@/features/analytics/queries';
import { usePageTitle } from '@/hooks/usePageTitle';
import { formatIst, formatPaise, toTelHref } from '@/lib/utils';

/** The customer's shop history — what makes this a useful profile instead of a row. */
export function AdminCustomerProfilePage() {
  const { customerId } = useParams<{ customerId: string }>();
  const customer = useCustomerProfile(customerId ?? null);
  const data = customer.data;
  usePageTitle(undefined, data ? `${data.name} · Customers · Admin` : 'Customer · Admin');

  return (
    <div className="container max-w-3xl space-y-4 py-5 pb-nav-safe md:pb-8">
      <Link
        to="/admin/customers"
        className="inline-flex min-h-touch items-center gap-1.5 text-sm font-semibold text-primary"
      >
        <ArrowLeft className="size-4" aria-hidden="true" /> Customers
      </Link>

      {customer.isPending ? (
        <div className="space-y-3">
          <Skeleton className="h-28" />
          <Skeleton className="h-36" />
        </div>
      ) : customer.isError ? (
        <p role="alert" className="rounded-lg bg-warning-soft p-3 text-sm text-warning">
          {customer.error.message}
        </p>
      ) : data ? (
        <>
          <Card>
            <CardHeader>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <CardTitle className="flex items-center gap-2 text-xl">
                    {data.name}
                    {data.is_top && (
                      <Star
                        className="size-4 fill-amber-400 text-amber-500"
                        aria-label="Top customer"
                      />
                    )}
                  </CardTitle>
                  <p className="mt-1 text-sm text-muted-foreground">
                    <Badge
                      tone={
                        data.tier === 'gold' || data.tier === 'platinum' ? 'success' : 'neutral'
                      }
                    >
                      {data.tier}
                    </Badge>
                    {data.referral_code && (
                      <span className="ml-2">Referral code {data.referral_code}</span>
                    )}
                  </p>
                </div>
                <div className="text-right">
                  <p className="text-xl font-extrabold tabular-nums">
                    {formatPaise(data.lifetime_spend_paise)}
                  </p>
                  <p className="text-xs text-muted-foreground">lifetime spend</p>
                </div>
              </div>
            </CardHeader>
            <CardContent className="grid gap-3 text-sm sm:grid-cols-2">
              <div>
                <p className="text-xs font-semibold uppercase text-muted-foreground">Phone</p>
                {data.phone ? (
                  <a className="font-semibold text-primary" href={toTelHref(data.phone)}>
                    {data.phone}
                  </a>
                ) : (
                  <p>Not provided</p>
                )}
              </div>
              <div>
                <p className="text-xs font-semibold uppercase text-muted-foreground">Email</p>
                <p className="break-all font-semibold">{data.email || 'Not provided'}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase text-muted-foreground">Orders</p>
                <p className="font-semibold">
                  {data.orders} · average {formatPaise(data.average_order_paise)}
                </p>
              </div>
              <div>
                <p className="flex items-center gap-1 text-xs font-semibold uppercase text-muted-foreground">
                  <MapPin className="size-3.5" aria-hidden="true" /> Saved addresses
                </p>
                <p className="font-semibold">{data.addresses}</p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase text-muted-foreground">First order</p>
                <p className="font-semibold">
                  {data.first_order_at ? formatIst(data.first_order_at) : 'None yet'}
                </p>
              </div>
              <div>
                <p className="text-xs font-semibold uppercase text-muted-foreground">
                  Most recent order
                </p>
                <p className="font-semibold">
                  {data.last_order_at ? formatIst(data.last_order_at) : 'None yet'}
                </p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex-row items-baseline justify-between gap-2">
              <CardTitle>Past orders</CardTitle>
              <span className="text-xs text-muted-foreground">
                {data.orders > data.recent_orders.length
                  ? `Showing the latest ${data.recent_orders.length} of ${data.orders}`
                  : `${data.recent_orders.length} total`}
              </span>
            </CardHeader>
            <CardContent className="space-y-2">
              {data.recent_orders.length === 0 ? (
                <p className="text-sm text-muted-foreground">No orders yet.</p>
              ) : (
                data.recent_orders.map((order) => (
                  <div
                    key={order.id}
                    className="flex min-h-touch items-center justify-between gap-3 rounded-lg border border-border px-3 py-2"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-semibold">{order.order_number}</p>
                      <p className="text-xs text-muted-foreground">
                        {formatIst(order.placed_at)} · {order.item_count} item
                        {order.item_count === 1 ? '' : 's'} · {order.status}
                      </p>
                    </div>
                    <p className="shrink-0 font-bold tabular-nums">
                      {formatPaise(order.total_paise)}
                    </p>
                  </div>
                ))
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
}
