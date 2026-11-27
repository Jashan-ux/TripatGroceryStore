import { Button } from '@/components/ui/button';
import { useStorePreview } from '@/features/store/StorePreviewContext';
import { useStoreConfig } from '@/hooks/useStoreConfig';
import { useCart } from '@/features/cart/useCart';
import { t } from '@/i18n';
import { MAX_LINE_QUANTITY, type CartLine } from '@/features/cart/types';
import { cn } from '@/lib/utils';

import { QuantityStepper } from './QuantityStepper';

export interface AddToCartProps {
  line: Omit<CartLine, 'quantity'>;
  /** Rendered when the line is not in the cart yet. */
  label?: string;
  size?: 'sm' | 'md';
  className?: string;
  /** Variants/products sold out: show why instead of a dead button. */
  disabledReason?: string;
}

/**
 * The one control that changes the basket. It reads and writes the cart
 * directly, so a product card, the product page and the cart page all stay in
 * sync without passing callbacks around.
 */
export function AddToCart({ line, label, size = 'sm', className, disabledReason }: AddToCartProps) {
  const cart = useCart();
  const quantity = cart.quantityOf(line.productId, line.variantId);
  const previewMode = useStorePreview();
  const config = useStoreConfig();

  if (previewMode) return null;

  if (config.data?.store_open === false) {
    return (
      <Button type="button" variant="secondary" disabled aria-label={t('cart.storeClosed')}>
        {t('cart.storeClosed')}
      </Button>
    );
  }

  if (disabledReason) {
    return (
      <Button
        variant="secondary"
        size={size}
        disabled
        className={className}
        aria-label={disabledReason}
      >
        {disabledReason}
      </Button>
    );
  }

  if (quantity === 0) {
    return (
      <Button
        variant="outline"
        size={size}
        className={cn('border-primary bg-primary-50 font-extrabold text-primary-800', className)}
        onClick={() => cart.add(line)}
        aria-label={`${t('cart.add')} ${line.name}${line.variantLabel ? ` (${line.variantLabel})` : ''} ${t('cart.toCart')}`}
      >
        {label ?? t('catalogue.addToCart')}
      </Button>
    );
  }

  return (
    <QuantityStepper
      quantity={quantity}
      max={Math.min(line.maxQuantity || MAX_LINE_QUANTITY, MAX_LINE_QUANTITY)}
      label={line.name}
      size={size}
      onDecrease={() => cart.setQuantity(line.productId, line.variantId, quantity - 1)}
      onIncrease={() => cart.setQuantity(line.productId, line.variantId, quantity + 1)}
      className={className}
    />
  );
}
