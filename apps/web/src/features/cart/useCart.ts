import { useContext } from 'react';

import { CartContext, type CartApi } from './context';

/** The cart, available anywhere below `CartProvider` (mounted in `App`). */
export function useCart(): CartApi {
  const cart = useContext(CartContext);
  if (!cart) throw new Error('useCart must be used inside <CartProvider>');
  return cart;
}
