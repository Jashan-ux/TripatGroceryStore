import { createContext } from 'react';

import type { CartLine } from './types';

/** Surface every cart consumer uses; implemented by `CartProvider`. */
export interface CartApi {
  lines: CartLine[];
  /** Total units, for the badge on the cart tab. */
  itemCount: number;
  /** Last-seen prices; the quote endpoint is the authority. */
  subtotalPaise: number;
  quantityOf: (productId: string, variantId: string | null) => number;
  add: (line: Omit<CartLine, 'quantity'>, quantity?: number) => void;
  setQuantity: (productId: string, variantId: string | null, quantity: number) => void;
  remove: (productId: string, variantId: string | null) => void;
  clear: () => void;
}

export const CartContext = createContext<CartApi | null>(null);
