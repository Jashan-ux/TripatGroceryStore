import { describe, expect, it } from 'vitest';

import { discountPercent, formatIst, formatPaise, toTelHref } from './utils';

describe('formatPaise', () => {
  it('renders whole rupees without decimals', () => {
    expect(formatPaise(50_000)).toContain('500');
    expect(formatPaise(50_000)).not.toContain('.00');
  });

  it('renders paise as two decimals', () => {
    expect(formatPaise(41_895)).toBe('₹418.95');
  });

  it('uses Indian digit grouping', () => {
    expect(formatPaise(1_00_00_000)).toBe('₹1,00,000');
  });

  it('handles zero', () => {
    expect(formatPaise(0)).toBe('₹0');
  });
});

describe('discountPercent', () => {
  it('is zero when the sale price is not below MRP', () => {
    expect(discountPercent(10_000, 10_000)).toBe(0);
    expect(discountPercent(10_000, 12_000)).toBe(0);
  });

  it('rounds to the nearest integer percentage', () => {
    expect(discountPercent(4_500, 4_140)).toBe(8);
    expect(discountPercent(12_000, 10_200)).toBe(15);
  });

  it('is zero for an invalid MRP', () => {
    expect(discountPercent(0, 500)).toBe(0);
  });
});

describe('formatIst', () => {
  it('formats in Asia/Kolkata regardless of the machine timezone', () => {
    // 2026-11-25T18:30:00Z is 26 Nov 2026, 00:00 IST.
    expect(formatIst('2026-11-25T18:30:00Z')).toBe('26 Nov 2026');
  });

  it('returns an empty string for garbage input', () => {
    expect(formatIst('not-a-date')).toBe('');
  });
});

describe('toTelHref', () => {
  it('strips spaces and dashes but keeps the country code', () => {
    expect(toTelHref('+91 87089-73386')).toBe('tel:+918708973386');
  });
});
