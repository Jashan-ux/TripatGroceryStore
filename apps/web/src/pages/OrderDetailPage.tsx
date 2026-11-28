import { ArrowLeft, CheckCircle2, MapPin, Phone, ReceiptText, Truck, XCircle } from 'lucide-react';
import { useState } from 'react';
import { Link, useParams, useSearchParams } from 'react-router-dom';

import { ProductThumb } from '@/components/catalogue/ProductCard';
import { EmptyState } from '@/components/common/EmptyState';
import { OrderTotals } from '@/components/orders/OrderTotals';
import { OrderStatusBadge } from '@/components/orders/OrderStatusBadge';
import { ReturnPanel } from '@/components/orders/ReturnPanel';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { useCancelOrder, useOrder } from '@/features/orders/queries';
import { canCancel } from '@/features/orders/status';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ApiError } from '@/lib/api';
import { formatDateOnly, formatIst, formatPaise } from '@/lib/utils';
import { t } from '@/i18n';
import { apiErrorMessage } from '@/i18n/messages';

/**
 * One order, end to end: what was ordered, where it is going, what it costs and
 * the store's own timeline. The timeline is built from order *events* (what
 * actually happened), not from the status field, so a cancelled-then-returned
 * order cannot rewrite its own history.
 */
export default function OrderDetailPage() {
  const { orderId } = useParams();
  const [params] = useSearchParams();
  const justPlaced = params.get('placed') === '1';

  const order = useOrder(orderId);
  usePageTitle(
    undefined,
    order.data ? `${t('orders.order')} ${order.data.order_number}` : t('orders.order'),
  );

  const cancel = useCancelOrder();
  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState('');
  const [cancelError, setCancelError] = useState<string | null>(null);

  if (order.isPending) {
    return (
      <div className="container max-w-3xl space-y-4 py-6" role="status" aria-live="polite">
        <span className="sr-only">{t('orders.detailLoading')}</span>
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-24 w-full rounded-xl" />
        <Skeleton className="h-40 w-full rounded-xl" />
      </div>
    );
  }

  if (order.isError || !order.data) {
    const notFound = order.error instanceof ApiError && order.error.status === 404;
    return (
      <div className="container max-w-3xl py-8">
        <EmptyState
          icon={ReceiptText}
          title={notFound ? t('orders.notFoundTitle') : t('orders.detailErrorTitle')}
          body={notFound ? t('orders.notFoundBody') : t('orders.detailErrorBody')}
          action={
            <Button asChild className="mt-2">
              <Link to="/orders">{t('orders.all')}</Link>
            </Button>
          }
        />
      </div>
    );
  }

  const data = order.data;
  const cancellable = canCancel(data.status);

  return (
    <div className="container max-w-3xl py-6 pb-nav-safe md:pb-8">
      <Link
        to="/orders"
        className="mb-3 inline-flex items-center gap-1 text-sm font-semibold text-primary"
      >
        <ArrowLeft className="size-4" aria-hidden="true" />
        {t('orders.all')}
      </Link>

      {justPlaced && (
        <div
          role="status"
          className="mb-4 flex items-start gap-2 rounded-xl bg-success-soft p-3 text-sm text-success"
        >
          <CheckCircle2 className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <div>
            <p className="font-bold">{t('orders.placedThanks')}</p>
            <p>
              {t('orders.callBefore').replace('{phone}', data.customer_phone)}
              {data.deliver_by
                ? `${t('orders.deliveryDatePrefix')}${formatDateOnly(data.deliver_by)}`
                : ''}
              . {formatPaise(data.total_paise)} {t('orders.keepCash')}
            </p>
          </div>
        </div>
      )}

      <header className="mb-4 rounded-xl border border-border bg-card p-4">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-lg font-extrabold tracking-tight">{data.order_number}</h1>
          <OrderStatusBadge status={data.status} />
        </div>
        <p className="mt-1 text-sm text-muted-foreground">
          {t('orders.placed')} {formatIst(data.placed_at)} · {data.item_count}{' '}
          {data.item_count === 1 ? t('orders.item') : t('orders.items')} ·{' '}
          {formatPaise(data.total_paise)}
        </p>
        {data.deliver_by && data.status !== 'cancelled' && data.status !== 'delivered' && (
          <p className="mt-2 flex items-center gap-1.5 text-sm font-medium">
            <Truck className="size-4 text-primary" aria-hidden="true" />
            {t('orders.expectedBy')}{' '}
            {formatDateOnly(data.deliver_by, { weekday: 'short', day: 'numeric', month: 'short' })}
          </p>
        )}
        {data.status === 'cancelled' && (
          <p className="mt-2 flex items-start gap-1.5 text-sm text-muted-foreground">
            <XCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            {t('orders.cancelled')} {data.cancelled_at ? formatIst(data.cancelled_at) : ''}
            {data.cancelled_reason ? ` — ${data.cancelled_reason}` : ''}
          </p>
        )}
      </header>

      <div className="grid gap-4 md:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="space-y-4">
          <section
            aria-labelledby="items-heading"
            className="rounded-xl border border-border bg-card"
          >
            <h2 id="items-heading" className="border-b border-border px-4 py-3 text-sm font-bold">
              {t('orders.itemsHeading')}
            </h2>
            <ul className="divide-y divide-border">
              {data.items.map((item) => (
                <li key={item.id} className="flex items-center gap-3 p-3">
                  <div className="size-12 shrink-0 overflow-hidden rounded-lg bg-secondary">
                    <ProductThumb name={item.name} imageUrl={item.image_url || null} size="sm" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold">{item.name}</p>
                    <p className="text-xs text-muted-foreground">
                      {[item.variant_label, item.unit_label].filter(Boolean).join(' · ')} ×{' '}
                      {item.quantity}
                    </p>
                  </div>
                  <span className="text-sm font-bold tabular-nums">
                    {formatPaise(item.line_total_paise)}
                  </span>
                </li>
              ))}
            </ul>
            <div className="border-t border-border p-4">
              <OrderTotals
                subtotalPaise={data.subtotal_paise}
                deliveryFeePaise={data.delivery_fee_paise}
                discountPaise={data.discount_paise}
                discountReason={data.discount_reason}
                walletPaise={data.wallet_paise}
                totalPaise={data.total_paise}
                itemCount={data.item_count}
              />
            </div>
          </section>

          <section
            aria-labelledby="timeline-heading"
            className="rounded-xl border border-border bg-card p-4"
          >
            <h2 id="timeline-heading" className="mb-3 text-sm font-bold">
              {t('orders.timeline')}
            </h2>
            <ol className="space-y-3">
              {[...data.events].reverse().map((event, index) => (
                <li key={`${event.created_at}-${index}`} className="flex gap-3">
                  <span
                    className="mt-1.5 size-2 shrink-0 rounded-full bg-primary"
                    aria-hidden="true"
                  />
                  <div className="text-sm">
                    <p className="font-semibold capitalize">
                      <OrderStatusBadge status={event.status} />
                      <span className="ml-2 font-normal text-muted-foreground">
                        {formatIst(event.created_at, {
                          day: 'numeric',
                          month: 'short',
                          hour: 'numeric',
                          minute: '2-digit',
                        })}
                      </span>
                    </p>
                    {event.note && <p className="text-muted-foreground">{event.note}</p>}
                  </div>
                </li>
              ))}
            </ol>
          </section>
        </div>

        <aside className="space-y-4">
          <section
            aria-labelledby="address-heading"
            className="rounded-xl border border-border bg-card p-4 text-sm"
          >
            <h2 id="address-heading" className="mb-2 flex items-center gap-2 font-bold">
              <MapPin className="size-4 text-primary" aria-hidden="true" />
              {t('orders.deliveringTo')}
            </h2>
            <p className="font-semibold">{data.address.recipient_name}</p>
            <p className="text-muted-foreground">
              {[
                [data.address.line1, data.address.line2].filter(Boolean).join(', '),
                data.address.landmark,
                data.address.city,
                data.address.state,
                data.address.pincode,
              ]
                .filter(Boolean)
                .join(', ')}
            </p>
            <p className="mt-2 flex items-center gap-1.5 text-muted-foreground">
              <Phone className="size-3.5" aria-hidden="true" />
              {data.customer_phone}
            </p>
            {data.customer_note && (
              <p className="mt-2 rounded-lg bg-muted/60 p-2 text-xs">“{data.customer_note}”</p>
            )}
          </section>

          <section className="rounded-xl border border-border bg-card p-4 text-sm">
            <h2 className="mb-1 font-bold">{t('orders.payment')}</h2>
            <p className="text-muted-foreground">
              {t('checkout.cod')} ·{' '}
              {data.payment_status === 'paid' ? t('orders.paid') : t('orders.toBePaid')}
            </p>
          </section>

          <ReturnPanel order={data} />

          {cancellable && (
            <section className="rounded-xl border border-border bg-card p-4">
              {confirming ? (
                <div className="space-y-2">
                  <p className="text-sm font-semibold">{t('orders.cancelQuestion')}</p>
                  <p className="text-xs text-muted-foreground">{t('orders.cancelExplainer')}</p>
                  <input
                    aria-label={t('orders.cancelReason')}
                    placeholder={t('orders.reasonOptional')}
                    value={reason}
                    maxLength={200}
                    onChange={(event) => setReason(event.target.value)}
                    className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm"
                  />
                  {cancelError && (
                    <p role="alert" className="text-xs text-primary-700">
                      {cancelError}
                    </p>
                  )}
                  <div className="flex gap-2">
                    <Button
                      variant="destructive"
                      size="sm"
                      disabled={cancel.isPending}
                      onClick={() =>
                        cancel.mutate(
                          { orderId: data.id, reason },
                          {
                            onSuccess: () => {
                              setConfirming(false);
                              setReason('');
                            },
                            onError: (error) =>
                              setCancelError(
                                error instanceof ApiError ? apiErrorMessage(error) : error.message,
                              ),
                          },
                        )
                      }
                    >
                      {cancel.isPending ? t('orders.cancelling') : t('orders.yesCancel')}
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setConfirming(false)}>
                      {t('orders.keepIt')}
                    </Button>
                  </div>
                </div>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  className="w-full"
                  onClick={() => setConfirming(true)}
                >
                  {t('orders.cancelOrder')}
                </Button>
              )}
            </section>
          )}
        </aside>
      </div>
    </div>
  );
}
