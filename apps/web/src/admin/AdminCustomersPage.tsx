import { Search, Star, UserRound } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { useAdminCustomers } from '@/features/analytics/queries';
import { usePageTitle } from '@/hooks/usePageTitle';
import { cn, formatIst, formatPaise } from '@/lib/utils';

const TIERS = [
  { value: '', label: 'Everyone' },
  { value: 'bronze', label: 'Bronze' },
  { value: 'silver', label: 'Silver' },
  { value: 'gold', label: 'Gold' },
  { value: 'platinum', label: 'Platinum' },
] as const;

/**
 * The people behind the orders.
 *
 * Search asks for a name, phone or email; the chips count actual members of each
 * loyalty tier across the shop, not just the 20 rows on this page. The top-three
 * star is not a decorative badge: the server ranks lifetime spend, the same
 * ranking that determines the gold/silver/bronze thresholds in the rewards code.
 * Every row opens one profile, because "customers" without a history is a phone
 * book, and the shop already has one.
 */
export function AdminCustomersPage() {
  usePageTitle(undefined, 'Customers · Admin');
  const [q, setQ] = useState('');
  const [tier, setTier] = useState('');
  const [sort, setSort] = useState('spend');
  const [page, setPage] = useState(1);
  const customers = useAdminCustomers({ q, tier, sort, page });
  const data = customers.data;

  return (
    <div className="container max-w-4xl space-y-4 py-5 pb-nav-safe md:pb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-extrabold tracking-tight">Customers</h1>
        <p className="text-xs text-muted-foreground">
          {data ? `${data.total} customer${data.total === 1 ? '' : 's'}` : 'Loading…'}
        </p>
      </div>

      <div className="relative block">
        <Search
          className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <Input
          aria-label="Search customers by name, phone or email"
          className="pl-9"
          placeholder="Name, phone or email"
          value={q}
          onChange={(event) => {
            setQ(event.target.value);
            setPage(1);
          }}
        />
      </div>

      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Filter by loyalty tier">
        {TIERS.map((item) => {
          const count = item.value ? (data?.counts[item.value] ?? 0) : data?.total;
          return (
            <button
              key={item.value || 'all'}
              type="button"
              aria-pressed={tier === item.value}
              onClick={() => {
                setTier(item.value);
                setPage(1);
              }}
              className={cn(
                'min-h-touch rounded-full px-3 text-sm font-semibold transition-colors',
                tier === item.value
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-muted text-muted-foreground hover:bg-muted/80',
              )}
            >
              {item.label} <span className="tabular-nums">{count ?? '—'}</span>
            </button>
          );
        })}
      </div>

      <label className="flex items-center justify-between gap-3 text-sm">
        <span className="text-muted-foreground">Sort by</span>
        <select
          aria-label="Sort customers"
          value={sort}
          onChange={(event) => {
            setSort(event.target.value);
            setPage(1);
          }}
          className="min-h-touch rounded-lg border border-border bg-background px-3 font-semibold"
        >
          <option value="spend">Lifetime spend</option>
          <option value="recent">Last order</option>
          <option value="newest">Newest first</option>
        </select>
      </label>

      {customers.isPending ? (
        <div className="space-y-2" aria-label="Loading customers">
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
          <Skeleton className="h-16" />
        </div>
      ) : customers.isError ? (
        <p role="alert" className="rounded-lg bg-warning-soft p-3 text-sm text-warning">
          {customers.error.message}
        </p>
      ) : !data ? null : data.items.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-8 text-center">
            <UserRound className="size-7 text-muted-foreground" aria-hidden="true" />
            <p className="font-semibold">No customers match that</p>
            <p className="text-sm text-muted-foreground">Try another name, phone or tier.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {data.items.map((customer) => (
            <Link
              key={customer.id}
              to={`/admin/customers/${customer.id}`}
              className="card-elev flex min-h-touch items-center justify-between gap-3 p-3 transition-shadow hover:shadow-md"
            >
              <div className="min-w-0">
                <p className="flex items-center gap-1.5 truncate font-bold">
                  {customer.name}
                  {customer.is_top && (
                    <Star
                      className="size-3.5 shrink-0 fill-amber-400 text-amber-500"
                      aria-label="Top customer"
                    />
                  )}
                </p>
                <p className="truncate text-xs text-muted-foreground">
                  {customer.phone || customer.email || 'No contact details'}
                  {customer.last_order_at && ` · Last order ${formatIst(customer.last_order_at)}`}
                </p>
              </div>
              <div className="shrink-0 text-right">
                <p className="font-bold tabular-nums">
                  {formatPaise(customer.lifetime_spend_paise)}
                </p>
                <p className="flex items-center justify-end gap-1.5 text-xs text-muted-foreground">
                  {customer.orders} order{customer.orders === 1 ? '' : 's'}
                  <Badge
                    tone={
                      customer.tier === 'gold' || customer.tier === 'platinum'
                        ? 'success'
                        : 'neutral'
                    }
                  >
                    {customer.tier}
                  </Badge>
                </p>
              </div>
            </Link>
          ))}
        </div>
      )}

      {data && data.total_pages > 1 && (
        <div className="flex items-center justify-between gap-3">
          <button
            type="button"
            className="min-h-touch rounded-lg border border-border px-3 text-sm font-semibold disabled:opacity-40"
            disabled={page <= 1}
            onClick={() => setPage((value) => value - 1)}
          >
            Previous
          </button>
          <p className="text-xs text-muted-foreground">
            Page {data.page} of {data.total_pages}
          </p>
          <button
            type="button"
            className="min-h-touch rounded-lg border border-border px-3 text-sm font-semibold disabled:opacity-40"
            disabled={page >= data.total_pages}
            onClick={() => setPage((value) => value + 1)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
