import { useEffect } from 'react';

import { t } from '@/i18n';

/**
 * Keeps the document title in sync with the active route.
 *
 * `literal` is for server-provided names (a product or category title): it wins
 * over the translated key so the tab and the installer name stay accurate.
 */
export function usePageTitle(titleKey?: string, literal?: string): void {
  useEffect(() => {
    const brand = t('brand.full');
    const title = literal?.trim() || (titleKey ? t(titleKey) : '');
    document.title = title ? `${title} · ${brand}` : brand;
  }, [titleKey, literal]);
}
