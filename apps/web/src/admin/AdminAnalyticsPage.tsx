import { ArrowUpRight, PackageX, Receipt, TrendingUp, Users, Wallet } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Skeleton } from '@/components/ui/skeleton';
import {
  useAnalyticsOrders,
  useAnalyticsSeries,
  useAnalyticsSummary,
  useLowStock,
  useTopProducts,
  type RangeParams,
} from '@/features/analytics/queries';
import { usePageTitle } from '@/hooks/usePageTitle';
import { cn, formatIst, formatPaise } from '@/lib/utils';

const RANGES = [
  { label: 'Today', days: 1 },
  { label: '7 days', days: 7 },
  { label: '30 days', days: 30 },
  { label: '90 days', days: 90 },
] as const;

/** Shop days are Haryana days; the API does the same conversion server-side. */
function shopToday(): Date {
  const now = new Date();
  return new Date(now.getTime() + (330 + now.getTimezoneOffset()) * 60_000);
}

function isoDate(date: Date): string {
  return date.toISOString().slice(0, 10);
}

function rangeFor(days: number): RangeParams {
  const end = shopToday();
  const start = new Date(end.getTime() - (days - 1) * 86_400_000);
  return { from: isoDate(start), to: isoDate(end) };
}

/**
 * The dashboard the owner actually opens.
 *
 * Everything here is one tap from the thing it counts: the revenue and orders
 * cards open the orders behind them (same range, same query predicate), the
 * "running out" list opens each product's own edit dialog, and the daily bars are
 * a plain SVG rather than a charting library — a customer's phone never downloads
 * an admin chart library, and the owner's does not need one either.
 *
 * The empty state is deliberate: a quiet day says "₹0" and "no orders in these
 * days", because a shop with two orders a day is the normal case, not an error.
 */
export function AdminAnalyticsPage() {
  usePageTitle(undefined, 'Analytics · Admin');
  const [days, setDays] = useState(30);
  const range = useMemo(() => rangeFor(days), [days]);
  const [drillDown, setDrillDown] = useState(false);

  const summary = useAnalyticsSummary(range);
  const series = useAnalyticsSeries(range);
  const products = useTopProducts(range);
  const lowStock = useLowStock();
  const orders = useAnalyticsOrders(range, drillDown);

  const data = summary.data;
  const peak = Math.max(1, ...(series.data?.points ?? []).map((point) => point.revenue_paise));

  return (
    <div className="container max-w-4xl space-y-4 py-5 pb-nav-safe md:pb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-extrabold tracking-tight">Analytics</h1>
        <p className="text-xs text-muted-foreground">
          {data ? `${data.range.from_date} → ${data.range.to_date}` : 'Loading…'}
        </p>
      </div>

      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Date range">
        {RANGES.map((option) => (
          <button
            key={option.days}
            type="button"
            aria-pressed={days === option.days}
            onClick={() => setDays(option.days)}
            className={cn(
              'min-h-touch rounded-full px-3 text-sm font-semibold transition-colors',
              days === option.days
                ? 'bg-primary text-primary-foreground'
                : 'bg-muted text-muted-foreground hover:bg-muted/80',
            )}
          >
            {option.label}
          </button>
        ))}
      </div>

      {summary.isPending ? (
        <div className="grid gap-3 sm:grid-cols-2">
          <Skeleton className="h-24" />
          <Skeleton className="h-24" />
        </div>
      ) : summary.isError ? (
        <p role="alert" className="rounded-lg bg-warning-soft p-3 text-sm text-warning">
          {summary.error.message}
        </p>
      ) : data ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2">
            <button
              type="button"
              onClick={() => setDrillDown((open) => !open)}
              aria-expanded={drillDown}
              className="card-elev p-4 text-left transition-shadow hover:shadow-md"
            >
              <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <TrendingUp className="size-3.5" aria-hidden="true" /> Revenue
              </p>
              <p className="mt-1 text-2xl font-extrabold tabular-nums">
                {formatPaise(data.revenue_paise)}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                {data.orders} order{data.orders === 1 ? '' : 's'} · avg{' '}
                {formatPaise(data.average_order_paise)} ·{' '}
                {drillDown ? 'hide the orders' : 'see the orders'}
                <ArrowUpRight className="ml-0.5 inline size-3" aria-hidden="true" />
              </p>
            </button>

            <div className="card-elev p-4">
              <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <Wallet className="size-3.5" aria-hidden="true" /> Cash still to collect
              </p>
              <p className="mt-1 text-2xl font-extrabold tabular-nums">
                {formatPaise(data.cash_pending_paise)}
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">on orders not yet delivered</p>
            </div>

            <div className="card-elev p-4">
              <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <Users className="size-3.5" aria-hidden="true" /> Customers
              </p>
              <p className="mt-1 text-2xl font-extrabold tabular-nums">
                {data.repeat_rate_percent}%
              </p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                came back · {data.new_customers} new · {data.repeat_customers} repeat
              </p>
            </div>

            <div className="card-elev p-4">
              <p className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                <Receipt className="size-3.5" aria-hidden="true" /> Items sold
              </p>
              <p className="mt-1 text-2xl font-extrabold tabular-nums">{data.items_sold}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">
                across {Object.entries(data.by_status).length} status
                {Object.entries(data.by_status).length === 1 ? '' : 'es'}
              </p>
            </div>
          </div>

          {drillDown && (
            <Card aria-label="Orders in this range">
              <CardHeader className="flex-row items-baseline justify-between gap-2">
                <CardTitle>The orders behind {formatPaise(data.revenue_paise)}</CardTitle>
                <span className="text-xs text-muted-foreground">
                  {orders.data ? `${orders.data.total} matching` : 'Loading…'}
                </span>
              </CardHeader>
              <CardContent className="space-y-1.5">
                {orders.isPending && <Skeleton className="h-16" />}
                {orders.data?.items.length === 0 && (
                  <p className="text-sm text-muted-foreground">No orders in these days.</p>
                )}
                {orders.data?.items.map((order) => (
                  <div
                    key={order.id}
                    className="flex items-baseline justify-between gap-2 border-b border-border/60 pb-1.5 text-sm last:border-0"
                  >
                    <div className="min-w-0">
                      <p className="truncate font-semibold">{order.order_number}</p>
                      <p className="truncate text-xs text-muted-foreground">
                        {order.customer_name} · {formatIst(order.placed_at)} · {order.status}
                      </p>
                    </div>
                    <p className="shrink-0 font-semibold tabular-nums">
                      {formatPaise(order.total_paise)}
                    </p>
                  </div>
                ))}
                {orders.data && orders.data.total_paise !== data.revenue_paise && (
                  <p role="alert" className="text-xs text-warning">
                    The list total ({formatPaise(orders.data.total_paise)}) disagrees with the card
                    ({formatPaise(data.revenue_paise)}). Do not trust either until we look.
                  </p>
                )}
                <Link
                  to="/admin/orders"
                  className="inline-flex min-h-touch items-center text-sm font-semibold text-primary"
                >
                  Open the order queue
                </Link>
              </CardContent>
            </Card>
          )}

          <Card aria-label="Revenue by day">
            <CardHeader>
              <CardTitle>Daily takings</CardTitle>
            </CardHeader>
            <CardContent>
              {series.isPending ? (
                <Skeleton className="h-24" />
              ) : (
                <>
                  <div
                    className="flex h-24 items-end gap-[2px]"
                    role="img"
                    aria-label="Revenue by day"
                  >
                    {(series.data?.points ?? []).map((point) => (
                      <div
                        key={point.day}
                        title={`${point.day}: ${formatPaise(point.revenue_paise)} · ${point.orders} order(s)`}
                        className={cn(
                          'flex-1 rounded-t-sm',
                          point.revenue_paise > 0 ? 'bg-primary' : 'bg-muted',
                        )}
                        style={{
                          height: `${Math.max(3, Math.round((point.revenue_paise / peak) * 100))}%`,
                        }}
                      />
                    ))}
                  </div>
                  <p className="mt-2 text-xs text-muted-foreground">
                    Tallest day {formatPaise(peak)}. Tap a bar&rsquo;s title for that day&rsquo;s
                    total.
                  </p>
                </>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}

      <div className="grid gap-3 md:grid-cols-2">
        <Card aria-label="What sold">
          <CardHeader className="flex-row items-baseline justify-between gap-2">
            <CardTitle>What sold</CardTitle>
            <Link to="/admin/products" className="text-xs font-semibold text-primary">
              Catalogue
            </Link>
          </CardHeader>
          <CardContent className="space-y-1.5">
            {products.isPending && <Skeleton className="h-20" />}
            {products.data?.items.length === 0 && (
              <p className="text-sm text-muted-foreground">Nothing sold in these days.</p>
            )}
            {products.data?.items.map((row) => (
              <div
                key={row.product_id}
                className="flex items-baseline justify-between gap-2 text-sm"
              >
                <p className="min-w-0 truncate">{row.name}</p>
                <p className="shrink-0 tabular-nums text-muted-foreground">
                  {row.units} × · {formatPaise(row.revenue_paise)}
                </p>
              </div>
            ))}
            {products.data && products.data.items.length > 0 && (
              <p className="pt-1 text-xs text-muted-foreground">
                {products.data.total_units} units · {formatPaise(products.data.total_revenue_paise)}{' '}
                in total
              </p>
            )}
          </CardContent>
        </Card>

        <Card aria-label="Running out">
          <CardHeader className="flex-row items-center gap-2">
            <PackageX className="size-4 text-warning" aria-hidden="true" />
            <CardTitle>Running out</CardTitle>
          </CardHeader>
          <CardContent className="space-y-1.5">
            {lowStock.isPending && <Skeleton className="h-20" />}
            {lowStock.data?.items.length === 0 && (
              <p className="text-sm text-muted-foreground">Everything is above its threshold.</p>
            )}
            {lowStock.data?.items.map((row) => (
              <Link
                key={row.product_id}
                to={row.edit_href}
                className="flex min-h-touch items-center justify-between gap-2 rounded-lg border border-border px-3 text-sm hover:bg-muted/60"
              >
                <span className="min-w-0 truncate font-semibold">{row.name}</span>
                <Badge tone={row.stock === 0 ? 'danger' : 'warning'}>
                  {row.stock === 0 ? 'Out' : `${row.stock} left`}
                </Badge>
              </Link>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
