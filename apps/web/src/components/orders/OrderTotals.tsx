import { t } from '@/i18n';
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
  discountReason,
  walletPaise = 0,
  totalPaise,
  itemCount,
  className,
}: {
  subtotalPaise: number;
  deliveryFeePaise: number;
  discountPaise: number;
  /** "Referral 10% off" — named, so the customer knows why the number moved. */
  discountReason?: string;
  /** Paid from the wallet; the total is what is left for cash. */
  walletPaise?: number;
  totalPaise: number;
  itemCount?: number;
  className?: string;
}) {
  return (
    <dl className={cn('space-y-1.5 text-sm', className)}>
      <div className="flex items-baseline justify-between">
        <dt className="text-muted-foreground">
          {t('cart.itemTotal')}
          {itemCount ? ` (${itemCount} ${itemCount === 1 ? t('cart.item') : t('cart.items')})` : ''}
        </dt>
        <dd className="font-medium tabular-nums">{formatPaise(subtotalPaise)}</dd>
      </div>
      <div className="flex items-baseline justify-between">
        <dt className="text-muted-foreground">{t('cart.delivery')}</dt>
        <dd className={cn('font-medium tabular-nums', deliveryFeePaise === 0 && 'text-success')}>
          {deliveryFeePaise === 0 ? t('cart.free') : formatPaise(deliveryFeePaise)}
        </dd>
      </div>
      {discountPaise > 0 && (
        <div className="flex items-baseline justify-between">
          <dt className="text-muted-foreground">{discountReason || t('cart.savings')}</dt>
          <dd className="font-medium tabular-nums text-success">−{formatPaise(discountPaise)}</dd>
        </div>
      )}
      {walletPaise > 0 && (
        <div className="flex items-baseline justify-between">
          <dt className="text-muted-foreground">{t('cart.fromWallet')}</dt>
          <dd className="font-medium tabular-nums text-success">−{formatPaise(walletPaise)}</dd>
        </div>
      )}
      <div className="flex items-baseline justify-between border-t border-border pt-2 text-base">
        <dt className="font-bold">{t('cart.toPay')}</dt>
        <dd className="font-extrabold tabular-nums">{formatPaise(totalPaise)}</dd>
      </div>
    </dl>
  );
}
