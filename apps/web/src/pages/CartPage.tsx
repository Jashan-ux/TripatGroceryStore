import { AlertTriangle, ShoppingBag, Trash2 } from 'lucide-react';
import { useMemo } from 'react';
import { Link } from 'react-router-dom';

import { ProductThumb } from '@/components/catalogue/ProductCard';
import { OrderTotals } from '@/components/orders/OrderTotals';
import { QuantityStepper } from '@/components/cart/QuantityStepper';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { EmptyState } from '@/components/common/EmptyState';
import { Skeleton } from '@/components/ui/skeleton';
import { useCart } from '@/features/cart/useCart';
import { MAX_LINE_QUANTITY, type CartLine } from '@/features/cart/types';
import { toQuoteItems, useQuote } from '@/features/orders/queries';
import { usePageTitle } from '@/hooks/usePageTitle';
import { useStoreConfig } from '@/hooks/useStoreConfig';
import { ApiError } from '@/lib/api';
import { formatPaise } from '@/lib/utils';
import { getCurrentLanguage, t } from '@/i18n';
import { blockingIssueMessage } from '@/i18n/messages';

/**
 * The basket.
 *
 * The cart (localStorage) decides *what* is in it; the API decides *what it
 * costs* and whether it can be delivered. When the two disagree — a product went
 * out of stock, the price moved, the total fell under the minimum — the quote
 * wins and the shopper is told why, in the same place they can fix it.
 */
export default function CartPage() {
  usePageTitle(undefined, t('cart.title'));
  const cart = useCart();
  const config = useStoreConfig();
  const items = useMemo(() => toQuoteItems(cart.lines), [cart.lines]);
  const quote = useQuote(items);

  const lineFor = (productId: string, variantId: string | null) =>
    quote.data?.lines.find(
      (line) => line.product_id === productId && (line.variant_id ?? null) === variantId,
    );

  if (cart.lines.length === 0) {
    return (
      <div className="container py-8">
        <h1 className="mb-4 text-xl font-extrabold tracking-tight">{t('cart.title')}</h1>
        <EmptyState
          icon={ShoppingBag}
          title={t('cart.emptyTitle')}
          body={t('cart.emptyBody')}
          action={
            <Button asChild className="mt-2">
              <Link to="/categories">{t('cart.startShopping')}</Link>
            </Button>
          }
        />
      </div>
    );
  }

  const totalQuantity = cart.lines.reduce((sum, line) => sum + line.quantity, 0);
  const offline = quote.error instanceof ApiError && quote.error.isOffline;

  return (
    <div className="container py-6 pb-nav-safe md:pb-8">
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <h1 className="text-xl font-extrabold tracking-tight">{t('cart.title')}</h1>
        <span className="text-sm text-muted-foreground">
          {totalQuantity} {totalQuantity === 1 ? t('cart.item') : t('cart.items')}
        </span>
      </div>

      {quote.isError && (
        <div
          role="alert"
          className="mb-4 flex items-start gap-2 rounded-xl border border-border bg-warning-soft p-3 text-sm text-warning"
        >
          <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <div className="flex-1">
            <p className="font-semibold">
              {offline ? t('cart.offlineTitle') : t('cart.priceErrorTitle')}
            </p>
            <p>{offline ? t('cart.offlineBody') : t('cart.priceErrorBody')}</p>
            <Button
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={() => void quote.refetch()}
            >
              {t('cart.retry')}
            </Button>
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_20rem]">
        <ul className="divide-y divide-border rounded-xl border border-border bg-card">
          {cart.lines.map((line) => (
            <CartRow
              key={`${line.productId}::${line.variantId ?? ''}`}
              line={line}
              quotedUnitPrice={lineFor(line.productId, line.variantId)?.unit_price_paise}
              quotedLineTotal={lineFor(line.productId, line.variantId)?.line_total_paise}
              issue={lineFor(line.productId, line.variantId)?.issue ?? null}
              availableStock={
                lineFor(line.productId, line.variantId)?.available_stock ?? line.maxQuantity
              }
              quantity={line.quantity}
              onQuantity={(quantity) => cart.setQuantity(line.productId, line.variantId, quantity)}
              onRemove={() => cart.remove(line.productId, line.variantId)}
            />
          ))}
        </ul>

        <aside className="space-y-4">
          <div className="rounded-xl border border-border bg-card p-4">
            <h2 className="mb-3 text-sm font-bold">{t('cart.billDetails')}</h2>
            {quote.data ? (
              <>
                <OrderTotals
                  subtotalPaise={quote.data.subtotal_paise}
                  deliveryFeePaise={quote.data.delivery_fee_paise}
                  discountPaise={quote.data.discount_paise}
                  totalPaise={quote.data.total_paise}
                  itemCount={quote.data.item_count}
                />
                <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
                  {quote.data.can_checkout
                    ? `${t('cart.deliveryBy')} ${new Date(quote.data.deliver_by).toLocaleDateString(
                        getCurrentLanguage() === 'hi' ? 'hi-IN' : 'en-IN',
                        {
                          day: 'numeric',
                          month: 'short',
                          timeZone: 'Asia/Kolkata',
                        },
                      )} · ${t('cart.cashOnDelivery')}`
                    : t('cart.fixItems')}
                </p>
              </>
            ) : (
              <div className="space-y-2" role="status" aria-live="polite">
                <span className="sr-only">Working out your bill</span>
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-6 w-3/4" />
              </div>
            )}

            {quote.data?.blocking_issues.map((issue) => (
              <p
                key={issue.code}
                role="alert"
                className="mt-3 flex items-start gap-1.5 text-xs font-medium text-warning"
              >
                <AlertTriangle className="mt-px size-3.5 shrink-0" aria-hidden="true" />
                {blockingIssueMessage(issue)}
              </p>
            ))}
          </div>

          <Button asChild size="lg" className="w-full">
            <Link
              to={quote.data?.can_checkout ? '/checkout' : '/cart'}
              aria-disabled={!quote.data?.can_checkout}
              onClick={(event) => {
                if (!quote.data?.can_checkout) event.preventDefault();
              }}
              className={quote.data?.can_checkout ? undefined : 'pointer-events-none opacity-60'}
            >
              {quote.data?.can_checkout
                ? `${t('cart.proceed')} · ${formatPaise(quote.data.total_paise)}`
                : t('cart.proceed')}
            </Link>
          </Button>
          {config.data?.store_phone && (
            <p className="text-center text-xs text-muted-foreground">
              {t('cart.needHelp')}{' '}
              <a
                href={`tel:${config.data.store_phone.replace(/[^\d+]/g, '')}`}
                className="font-semibold text-primary"
              >
                {config.data.store_phone}
              </a>
            </p>
          )}
        </aside>
      </div>
    </div>
  );
}

function CartRow({
  line,
  quotedUnitPrice,
  quotedLineTotal,
  issue,
  availableStock,
  quantity,
  onQuantity,
  onRemove,
}: {
  line: CartLine;
  quotedUnitPrice?: number;
  quotedLineTotal?: number;
  issue: 'out_of_stock' | 'partially_available' | 'unavailable' | null;
  availableStock: number;
  quantity: number;
  onQuantity: (quantity: number) => void;
  onRemove: () => void;
}) {
  const unitPrice = quotedUnitPrice ?? line.pricePaise;
  const lineTotal = quotedLineTotal ?? unitPrice * quantity;
  const max = Math.min(Math.max(availableStock, quantity), MAX_LINE_QUANTITY);

  return (
    <li className="flex gap-3 p-3">
      <Link
        to={line.slug ? `/products/${line.slug}` : '/categories'}
        className="size-16 shrink-0 overflow-hidden rounded-lg bg-secondary"
        aria-hidden="true"
        tabIndex={-1}
      >
        <ProductThumb name={line.name} imageUrl={line.imageUrl} size="sm" />
      </Link>

      <div className="min-w-0 flex-1">
        <Link
          to={line.slug ? `/products/${line.slug}` : '/categories'}
          className="line-clamp-2 text-sm font-semibold hover:text-primary-700"
        >
          {line.name}
        </Link>
        <p className="text-xs text-muted-foreground">
          {[line.variantLabel, line.unitLabel].filter(Boolean).join(' · ')}
        </p>
        <p className="mt-0.5 text-sm font-medium tabular-nums">{formatPaise(unitPrice)}</p>

        {issue && (
          <Badge tone="warning" className="mt-1.5">
            {issue === 'out_of_stock'
              ? t('cart.outOfStockRemove')
              : issue === 'partially_available'
                ? `${t('cart.onlyLeft')} ${availableStock} ${t('catalogue.left')}`
                : t('cart.noLongerSold')}
          </Badge>
        )}

        <div className="mt-2 flex items-center justify-between gap-2">
          <QuantityStepper
            quantity={quantity}
            max={max}
            label={line.name}
            onDecrease={() => onQuantity(quantity - 1)}
            onIncrease={() => onQuantity(quantity + 1)}
          />
          <span className="text-sm font-bold tabular-nums">{formatPaise(lineTotal)}</span>
        </div>
      </div>

      <button
        type="button"
        onClick={onRemove}
        className="self-start rounded-lg p-2 text-muted-foreground hover:bg-secondary hover:text-destructive"
        aria-label={t('cart.removeFromCartAria').replace('{product}', line.name)}
      >
        <Trash2 className="size-4" aria-hidden="true" />
      </button>
    </li>
  );
}
