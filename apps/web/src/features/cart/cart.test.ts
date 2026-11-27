import { describe, expect, it } from 'vitest';

import { CART_STORAGE_KEY, loadCart, parseCart, saveCart } from '@/features/cart/storage';
import {
  MAX_LINE_QUANTITY,
  clampQuantity,
  countLines,
  lineKey,
  previewSubtotalPaise,
  reduceCart,
  type CartLine,
  type CartState,
} from '@/features/cart/types';

function line(overrides: Partial<CartLine> = {}): CartLine {
  return {
    productId: 'p1',
    variantId: null,
    slug: 'palak',
    name: 'Palak',
    unitLabel: '250 g',
    variantLabel: '',
    imageUrl: null,
    pricePaise: 2500,
    maxQuantity: 5,
    quantity: 1,
    ...overrides,
  };
}

const empty: CartState = { lines: [] };

describe('cart reducer', () => {
  it('adds a line and defaults to one unit', () => {
    const state = reduceCart(empty, { type: 'add', line: line() });
    expect(state.lines).toHaveLength(1);
    expect(state.lines[0]?.quantity).toBe(1);
  });

  it('merges a repeat add into the existing line instead of duplicating it', () => {
    const once = reduceCart(empty, { type: 'add', line: line() });
    const twice = reduceCart(once, { type: 'add', line: line(), quantity: 2 });
    expect(twice.lines).toHaveLength(1);
    expect(twice.lines[0]?.quantity).toBe(3);
  });

  it('treats a different variant of the same product as a separate line', () => {
    const state = reduceCart(reduceCart(empty, { type: 'add', line: line() }), {
      type: 'add',
      line: line({ variantId: 'v2', variantLabel: '1 kg' }),
    });
    expect(state.lines).toHaveLength(2);
    expect(lineKey('p1', null)).not.toBe(lineKey('p1', 'v2'));
  });

  it('never sells more than the shelf has', () => {
    const state = reduceCart(empty, { type: 'add', line: line(), quantity: 9 });
    expect(state.lines[0]?.quantity).toBe(5);
    expect(clampQuantity(50, 5)).toBe(5);
    expect(clampQuantity(50, 1000)).toBe(MAX_LINE_QUANTITY);
  });

  it('refuses to add a sold-out line', () => {
    const state = reduceCart(empty, { type: 'add', line: line({ maxQuantity: 0 }) });
    expect(state.lines[0]?.quantity).toBe(1);
    expect(
      reduceCart(empty, { type: 'add', line: line({ maxQuantity: 0 }), quantity: 0 }).lines,
    ).toHaveLength(0);
  });

  it('removes the line when quantity is set to zero', () => {
    const added = reduceCart(empty, { type: 'add', line: line() });
    const state = reduceCart(added, { type: 'setQuantity', key: lineKey('p1', null), quantity: 0 });
    expect(state.lines).toHaveLength(0);
  });

  it('clamps an increase past stock and ignores an unknown key', () => {
    const added = reduceCart(empty, { type: 'add', line: line() });
    const bumped = reduceCart(added, {
      type: 'setQuantity',
      key: lineKey('p1', null),
      quantity: 99,
    });
    expect(bumped.lines[0]?.quantity).toBe(5);
    expect(reduceCart(added, { type: 'setQuantity', key: 'nope', quantity: 2 })).toBe(added);
  });

  it('removes, clears and replaces', () => {
    const two = reduceCart(reduceCart(empty, { type: 'add', line: line() }), {
      type: 'add',
      line: line({ productId: 'p2', name: 'Aloo' }),
    });
    expect(reduceCart(two, { type: 'remove', key: lineKey('p1', null) }).lines).toHaveLength(1);
    expect(reduceCart(two, { type: 'clear' }).lines).toHaveLength(0);
    expect(
      reduceCart(empty, { type: 'replace', lines: [line({ quantity: 99 })] }).lines[0]?.quantity,
    ).toBe(5);
  });

  it('counts units, not lines, and previews the last seen prices', () => {
    const state = reduceCart(
      reduceCart(empty, { type: 'add', line: line({ maxQuantity: 10 }), quantity: 2 }),
      {
        type: 'add',
        line: line({ productId: 'p2', pricePaise: 1000, maxQuantity: 10 }),
        quantity: 3,
      },
    );
    expect(countLines(state.lines)).toBe(5);
    expect(previewSubtotalPaise(state.lines)).toBe(2 * 2500 + 3 * 1000);
  });
});

describe('cart storage', () => {
  it('round-trips through storage', () => {
    const store = window.localStorage;
    saveCart({ lines: [line({ quantity: 2 })] }, store);
    expect(loadCart(store).lines[0]?.quantity).toBe(2);
    store.clear();
    expect(loadCart(store).lines).toHaveLength(0);
  });

  it('drops anything that is not a valid line', () => {
    const parsed = parseCart({
      lines: [
        { productId: 'ok', variantId: null, name: 'Palak', quantity: 2 },
        { productId: '', name: 'No id', quantity: 1 },
        { productId: 'x', name: 'Zero', quantity: 0 },
        { productId: 'y', name: 'Negative', quantity: -3 },
        null,
        'nope',
      ],
    });
    expect(parsed.lines).toHaveLength(1);
    // Missing display fields get sane defaults rather than `undefined`.
    expect(parsed.lines[0]).toMatchObject({
      name: 'Palak',
      pricePaise: 0,
      maxQuantity: 20,
      slug: '',
    });
  });

  it('survives corrupt JSON and unexpected shapes', () => {
    window.localStorage.setItem(CART_STORAGE_KEY, '{not json');
    expect(loadCart(window.localStorage).lines).toHaveLength(0);
    window.localStorage.setItem(CART_STORAGE_KEY, '"a string"');
    expect(loadCart(window.localStorage).lines).toHaveLength(0);
    window.localStorage.removeItem(CART_STORAGE_KEY);
    expect(loadCart().lines).toHaveLength(0);
  });

  it('clamps a stored quantity that is past the remembered stock', () => {
    expect(
      parseCart({ lines: [{ ...line(), quantity: 40, maxQuantity: 3 }] }).lines[0]?.quantity,
    ).toBe(3);
  });
});
