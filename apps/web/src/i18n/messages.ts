import type { BlockingIssue } from '@tripat/api-client';

import { t } from '@/i18n';
import type { ApiError } from '@/lib/api';
import { formatPaise } from '@/lib/utils';

/** Translate API-known checkout blockers while retaining server copy as a safe fallback. */
export function apiErrorMessage(error: ApiError): string {
  if (error.code === 'minimum_order_not_met' && typeof error.details.shortfall_paise === 'number') {
    return t('checkout.addMoreToCheckout').replace(
      '{amount}',
      formatPaise(error.details.shortfall_paise),
    );
  }
  if (error.code === 'store_closed') return t('cart.storeClosedIssue');
  if (error.code === 'pincode_not_serviceable') return t('cart.pincodeIssue');
  if (error.code === 'insufficient_stock') return t('cart.stockIssue');
  return error.message;
}

export function blockingIssueMessage(issue: BlockingIssue): string {
  switch (issue.code) {
    case 'stock':
      return t('cart.stockIssue');
    case 'minimum_order': {
      const minimum = issue.details?.minimum_order_paise;
      const shortfall = issue.details?.shortfall_paise;
      if (typeof minimum !== 'number' || typeof shortfall !== 'number') return issue.message;
      return t('cart.minimumOrderIssue')
        .replace('{min}', formatPaise(minimum))
        .replace('{shortfall}', formatPaise(shortfall));
    }
    case 'pincode':
      return t('cart.pincodeIssue');
    case 'store_closed':
      return t('cart.storeClosedIssue');
    default:
      return issue.message;
  }
}
