import { cn, formatPaise } from '@/lib/utils';

/**
 * Money summary row set. Every amount is integer paise computed by the API;
 * this component only formats. Delivery is shown as "FREE" rather than ₹0 so
 * the shopper reads it as a benefit, not a charge.
 */
export function OrderTotals({
  subtotalPaise,
  deliveryFeePaise,
  discountPaise,
  totalPaise,
  itemCount,
  className,
}: {
  subtotalPaise: number;
  deliveryFeePaise: number;
  discountPaise: number;
  totalPaise: number;
  itemCount?: number;
  className?: string;
}) {
  return (
    <dl className={cn('space-y-1.5 text-sm', className)}>
      <div className="flex items-baseline justify-between">
        <dt className="text-muted-foreground">
          Item total{itemCount ? ` (${itemCount} item${itemCount === 1 ? '' : 's'})` : ''}
        </dt>
        <dd className="font-medium tabular-nums">{formatPaise(subtotalPaise)}</dd>
      </div>
      <div className="flex items-baseline justify-between">
        <dt className="text-muted-foreground">Delivery</dt>
        <dd className={cn('font-medium tabular-nums', deliveryFeePaise === 0 && 'text-success')}>
          {deliveryFeePaise === 0 ? 'FREE' : formatPaise(deliveryFeePaise)}
        </dd>
      </div>
      {discountPaise > 0 && (
        <div className="flex items-baseline justify-between">
          <dt className="text-muted-foreground">Savings</dt>
          <dd className="font-medium tabular-nums text-success">−{formatPaise(discountPaise)}</dd>
        </div>
      )}
      <div className="flex items-baseline justify-between border-t border-border pt-2 text-base">
        <dt className="font-bold">To pay</dt>
        <dd className="font-extrabold tabular-nums">{formatPaise(totalPaise)}</dd>
      </div>
    </dl>
  );
}
