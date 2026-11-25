/**
 * Guest cart model.
 *
 * The cart is *not* a source of truth for money: it only remembers which
 * product/variant the shopper picked and how many, plus enough display metadata
 * (name, unit, image) to paint the basket before the quote arrives. Prices and
 * totals always come from `POST /api/v1/checkout/quote`, so a stale cart can
 * never show a stale price.
 */
export interface CartLine {
  productId: string;
  variantId: string | null;
  /** Display metadata, refreshed whenever the shopper adds the line again. */
  slug: string;
  name: string;
  unitLabel: string;
  variantLabel: string;
  imageUrl: string | null;
  /** Last seen unit price — for a "price changed" hint, never for the total. */
  pricePaise: number;
  /** Highest quantity the store can currently serve for this line. */
  maxQuantity: number;
  quantity: number;
}

export interface CartState {
  lines: CartLine[];
}

/** A single line can never exceed this, whatever the stock says. */
export const MAX_LINE_QUANTITY = 20;

/** Stable identity for a product/variant pair. */
export function lineKey(productId: string, variantId: string | null): string {
  return `${productId}::${variantId ?? ''}`;
}

export type CartAction =
  | { type: 'add'; line: Omit<CartLine, 'quantity'>; quantity?: number }
  | { type: 'setQuantity'; key: string; quantity: number }
  | { type: 'remove'; key: string }
  | { type: 'clear' }
  | { type: 'replace'; lines: CartLine[] };

/** Never add more than the shelf can serve. */
export function clampQuantity(quantity: number, maxQuantity: number): number {
  const ceiling = Math.max(1, Math.min(maxQuantity || MAX_LINE_QUANTITY, MAX_LINE_QUANTITY));
  return Math.max(0, Math.min(Math.trunc(quantity), ceiling));
}

export function clampLine(line: CartLine): CartLine {
  return { ...line, quantity: clampQuantity(line.quantity, line.maxQuantity) };
}

export function countLines(lines: CartLine[]): number {
  return lines.reduce((sum, line) => sum + line.quantity, 0);
}

/** Subtotal from the last seen prices — a preview only, the quote is authoritative. */
export function previewSubtotalPaise(lines: CartLine[]): number {
  return lines.reduce((sum, line) => sum + line.pricePaise * line.quantity, 0);
}

export function reduceCart(state: CartState, action: CartAction): CartState {
  switch (action.type) {
    case 'add': {
      const key = lineKey(action.line.productId, action.line.variantId);
      const wanted = action.quantity ?? 1;
      const existing = state.lines.find((line) => lineKey(line.productId, line.variantId) === key);
      if (existing) {
        const quantity = clampQuantity(existing.quantity + wanted, action.line.maxQuantity);
        return {
          lines: state.lines.map((line) =>
            line === existing ? { ...action.line, quantity } : line,
          ),
        };
      }
      const quantity = clampQuantity(wanted, action.line.maxQuantity);
      if (quantity <= 0) return state;
      return { lines: [...state.lines, { ...action.line, quantity }] };
    }
    case 'setQuantity': {
      const next = state.lines
        .map((line) => (lineKey(line.productId, line.variantId) === action.key ? line : null))
        .find((line) => line !== null);
      if (!next) return state;
      const quantity = clampQuantity(action.quantity, next.maxQuantity);
      if (quantity <= 0) {
        return {
          lines: state.lines.filter(
            (line) => lineKey(line.productId, line.variantId) !== action.key,
          ),
        };
      }
      return {
        lines: state.lines.map((line) =>
          lineKey(line.productId, line.variantId) === action.key ? { ...line, quantity } : line,
        ),
      };
    }
    case 'remove':
      return {
        lines: state.lines.filter((line) => lineKey(line.productId, line.variantId) !== action.key),
      };
    case 'clear':
      return { lines: [] };
    case 'replace':
      return { lines: action.lines.map(clampLine) };
  }
}
