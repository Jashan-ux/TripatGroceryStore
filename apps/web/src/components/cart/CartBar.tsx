import { ShoppingBag } from 'lucide-react';
import { Link, useLocation } from 'react-router-dom';

import { useCart } from '@/features/cart/useCart';
import { formatPaise } from '@/lib/utils';

/**
 * Sticky basket summary for phones: item count, the cart's own preview total and
 * one tap to the cart. Hidden on the cart and checkout pages (where the basket
 * *is* the page) and on desktop, where the header carries the cart link.
 *
 * It sits directly above the bottom nav rather than on top of it, and pages
 * using it reserve space with `.pb-cart-safe`.
 */
export function CartBar() {
  const cart = useCart();
  const { pathname } = useLocation();
  const hidden = cart.itemCount === 0 || pathname === '/cart' || pathname.startsWith('/checkout');

  if (hidden) return null;

  return (
    <div className="fixed inset-x-0 bottom-[calc(var(--bottom-nav-height)+env(safe-area-inset-bottom))] z-30 px-3 pb-2 md:hidden">
      <Link
        to="/cart"
        className="mx-auto flex max-w-lg items-center justify-between gap-3 rounded-xl bg-primary px-4 py-2.5 text-primary-foreground shadow-elev2"
        aria-label={`View cart: ${cart.itemCount} item${cart.itemCount === 1 ? '' : 's'}, ${formatPaise(cart.subtotalPaise)}`}
      >
        <span className="flex items-center gap-2 text-sm font-semibold">
          <ShoppingBag className="size-4" aria-hidden="true" />
          {cart.itemCount} item{cart.itemCount === 1 ? '' : 's'}
        </span>
        <span className="text-sm font-extrabold tabular-nums">
          {formatPaise(cart.subtotalPaise)}
        </span>
        <span className="rounded-lg bg-white/20 px-2 py-1 text-xs font-bold">View cart</span>
      </Link>
    </div>
  );
}
