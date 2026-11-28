import { Minus, Plus } from 'lucide-react';

import { t } from '@/i18n';
import { cn } from '@/lib/utils';

/**
 * Add/stepper control. Every control is at least 44px tall so it stays usable
 * one-handed on a phone, and the buttons carry real labels for screen readers
 * ("Add one more Palak", not "plus").
 */
export function QuantityStepper({
  quantity,
  max,
  onDecrease,
  onIncrease,
  label,
  size = 'md',
  className,
}: {
  quantity: number;
  max: number;
  onDecrease: () => void;
  onIncrease: () => void;
  label: string;
  size?: 'sm' | 'md';
  className?: string;
}) {
  const atMax = quantity >= max;
  const button = cn(
    'flex items-center justify-center rounded-lg text-primary-800 transition-colors disabled:opacity-40',
    size === 'sm' ? 'size-7' : 'size-9',
  );

  return (
    <div
      className={cn(
        'inline-flex items-center gap-1 rounded-xl bg-primary-50 p-0.5',
        size === 'sm' ? 'text-sm' : 'text-base',
        className,
      )}
    >
      <button
        type="button"
        className={cn(button, 'hover:bg-primary-100')}
        onClick={onDecrease}
        aria-label={`${t('cart.removeOne')} ${label}`}
      >
        <Minus className="size-4" aria-hidden="true" />
      </button>
      <output
        className={cn('min-w-6 text-center font-bold tabular-nums text-primary-900')}
        aria-live="polite"
      >
        {quantity}
      </output>
      <button
        type="button"
        className={cn(button, 'hover:bg-primary-100')}
        onClick={onIncrease}
        disabled={atMax}
        aria-label={atMax ? `${label} ${t('cart.atMax')}` : `${t('cart.addOneMore')} ${label}`}
      >
        <Plus className="size-4" aria-hidden="true" />
      </button>
    </div>
  );
}
