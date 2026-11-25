/**
 * Cart persistence.
 *
 * Only ids, quantities and display metadata are stored — never prices or
 * totals. Anything that fails validation is dropped rather than migrated,
 * because a wrong basket is worse than an empty one.
 */
import { clampLine, type CartLine, type CartState } from './types';

export const CART_STORAGE_KEY = 'tripat.cart.v1';

const EMPTY: CartState = { lines: [] };

function isLine(value: unknown): value is CartLine {
  if (!value || typeof value !== 'object') return false;
  const line = value as Record<string, unknown>;
  return (
    typeof line.productId === 'string' &&
    line.productId.length > 0 &&
    (line.variantId === null || typeof line.variantId === 'string') &&
    typeof line.name === 'string' &&
    typeof line.quantity === 'number' &&
    Number.isFinite(line.quantity) &&
    line.quantity > 0
  );
}

/** Coerce a decoded payload into a valid cart, filling in missing display fields. */
export function parseCart(raw: unknown): CartState {
  if (!raw || typeof raw !== 'object') return EMPTY;
  const lines = (raw as { lines?: unknown }).lines;
  if (!Array.isArray(lines)) return EMPTY;
  return {
    lines: lines.filter(isLine).map((line) =>
      clampLine({
        productId: line.productId,
        variantId: line.variantId ?? null,
        slug: typeof line.slug === 'string' ? line.slug : '',
        name: line.name,
        unitLabel: typeof line.unitLabel === 'string' ? line.unitLabel : '',
        variantLabel: typeof line.variantLabel === 'string' ? line.variantLabel : '',
        imageUrl: typeof line.imageUrl === 'string' ? line.imageUrl : null,
        pricePaise: Number.isFinite(line.pricePaise) ? line.pricePaise : 0,
        maxQuantity:
          Number.isFinite(line.maxQuantity) && line.maxQuantity > 0 ? line.maxQuantity : 20,
        quantity: line.quantity,
      }),
    ),
  };
}

export function loadCart(storage?: Storage): CartState {
  const store = storage ?? safeStorage();
  if (!store) return EMPTY;
  try {
    const raw = store.getItem(CART_STORAGE_KEY);
    if (!raw) return EMPTY;
    return parseCart(JSON.parse(raw));
  } catch {
    return EMPTY;
  }
}

export function saveCart(state: CartState, storage?: Storage): void {
  const store = storage ?? safeStorage();
  if (!store) return;
  try {
    store.setItem(CART_STORAGE_KEY, JSON.stringify(state));
  } catch {
    // Private mode / quota: the cart stays in memory for this session.
  }
}

/** Safari private mode throws on access, so guard the lookup itself. */
function safeStorage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}
