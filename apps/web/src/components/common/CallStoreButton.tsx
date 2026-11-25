import { Phone } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { useStoreConfig } from '@/hooks/useStoreConfig';
import { t } from '@/i18n';
import { toTelHref } from '@/lib/utils';

/**
 * Tap-to-call. The number comes from store settings via the API so the merchant
 * can change it without a deploy, and it is never hard-coded in a component.
 */
export function CallStoreButton({ className }: { className?: string }) {
  const { data } = useStoreConfig();
  const phone = data?.store_phone;
  if (!phone) return null;
  return (
    <Button asChild variant="outline" className={className}>
      <a href={toTelHref(phone)} aria-label={`${t('home.callStore')} ${phone}`}>
        <Phone aria-hidden="true" />
        <span>{phone}</span>
      </a>
    </Button>
  );
}
