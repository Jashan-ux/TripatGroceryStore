/** Which order statuses the store still lets a shopper call off. */
export const CANCELLABLE_STATUSES = new Set(['processing']);

export function canCancel(status: string): boolean {
  return CANCELLABLE_STATUSES.has(status);
}
