import { useEffect } from 'react';

import { t } from '@/i18n';

/** Keeps the document title in sync with the active route. */
export function usePageTitle(titleKey?: string): void {
  useEffect(() => {
    const brand = t('brand.full');
    document.title = titleKey ? `${t(titleKey)} · ${brand}` : brand;
  }, [titleKey]);
}
