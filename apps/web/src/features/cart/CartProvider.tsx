import { useEffect, useMemo, useReducer, useRef } from 'react';
import type { ReactNode } from 'react';

import { CartContext, type CartApi } from './context';
import { CART_STORAGE_KEY, loadCart, saveCart } from './storage';
import { countLines, lineKey, previewSubtotalPaise, reduceCart, type CartLine } from './types';

export function CartProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(reduceCart, null, () => loadCart());
  const first = useRef(true);
  // Mirrors the current lines for event handlers, which must not read state
  // captured by a stale closure.
  const linesRef = useRef(state.lines);
  useEffect(() => {
    linesRef.current = state.lines;
  }, [state.lines]);

  // Persist after every change, but not on mount (that would rewrite storage
  // just because a page loaded).
  useEffect(() => {
    if (first.current) {
      first.current = false;
      return;
    }
    saveCart(state);
  }, [state]);

  // Another tab changed the cart: adopt it, so two tabs never disagree. The
  // `storage` event never fires for the tab that wrote the value, so this can
  // not loop back into the persist effect above.
  useEffect(() => {
    const reload = (event: StorageEvent) => {
      if (event.key !== null && event.key !== CART_STORAGE_KEY) return;
      const incoming = loadCart().lines;
      if (!sameLines(linesRef.current, incoming)) {
        dispatch({ type: 'replace', lines: incoming });
      }
    };
    window.addEventListener('storage', reload);
    return () => window.removeEventListener('storage', reload);
  }, []);

  const api = useMemo<CartApi>(
    () => ({
      lines: state.lines,
      itemCount: countLines(state.lines),
      subtotalPaise: previewSubtotalPaise(state.lines),
      quantityOf: (productId, variantId) =>
        state.lines.find((line) => line.productId === productId && line.variantId === variantId)
          ?.quantity ?? 0,
      add: (line, quantity = 1) => dispatch({ type: 'add', line, quantity }),
      setQuantity: (productId, variantId, quantity) =>
        dispatch({ type: 'setQuantity', key: lineKey(productId, variantId), quantity }),
      remove: (productId, variantId) =>
        dispatch({ type: 'remove', key: lineKey(productId, variantId) }),
      clear: () => dispatch({ type: 'clear' }),
    }),
    [state.lines],
  );

  return <CartContext.Provider value={api}>{children}</CartContext.Provider>;
}

/** Structural comparison, so an unrelated storage write cannot re-render the cart. */
function sameLines(a: CartLine[], b: CartLine[]): boolean {
  if (a.length !== b.length) return false;
  return a.every((line, index) => {
    const other = b[index];
    return (
      other !== undefined &&
      lineKey(line.productId, line.variantId) === lineKey(other.productId, other.variantId) &&
      line.quantity === other.quantity
    );
  });
}
