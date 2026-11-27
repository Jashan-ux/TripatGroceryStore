import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

/** Merge conditional class names with Tailwind conflict resolution. */
export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

/**
 * Format integer paise as Indian rupees. Money is *never* a float anywhere in
 * this codebase; the only place it becomes a decimal is at render time.
 */
export function formatPaise(paise: number, options: { decimals?: boolean } = {}): string {
  const rupees = paise / 100;
  const hasFraction = paise % 100 !== 0;
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    minimumFractionDigits: hasFraction || options.decimals ? 2 : 0,
    maximumFractionDigits: 2,
  }).format(rupees);
}

/** Percentage discount shown when MRP is higher than the sale price. */
export function discountPercent(mrpPaise: number, pricePaise: number): number {
  if (mrpPaise <= pricePaise || mrpPaise <= 0) return 0;
  return Math.round(((mrpPaise - pricePaise) / mrpPaise) * 100);
}

/** Format an ISO timestamp in Asia/Kolkata, whatever the device timezone is. */
export function formatIst(
  iso: string,
  options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short', year: 'numeric' },
): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat('en-IN', { ...options, timeZone: 'Asia/Kolkata' }).format(date);
}

/**
 * Format a *date-only* string (`2026-11-26`, as the API sends `deliver_by`)
 * without timezone drift: parse it as noon UTC so no offset can move the day.
 */
export function formatDateOnly(
  iso: string,
  options: Intl.DateTimeFormatOptions = { day: 'numeric', month: 'short' },
): string {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!match) return formatIst(iso, options);
  const date = new Date(Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 12));
  return new Intl.DateTimeFormat('en-IN', { ...options, timeZone: 'Asia/Kolkata' }).format(date);
}

/** Tel-safe href: "+91 87089-73386" → "tel:+918708973386". */
export function toTelHref(phone: string): string {
  return `tel:${phone.replace(/[^\d+]/g, '')}`;
}
