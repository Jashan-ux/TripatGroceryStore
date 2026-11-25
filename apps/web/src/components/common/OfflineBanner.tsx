import { WifiOff } from 'lucide-react';

import { useOnlineStatus } from '@/hooks/useOnlineStatus';
import { t } from '@/i18n';

/** Persistent, non-blocking notice while the device is offline. */
export function OfflineBanner() {
  const online = useOnlineStatus();
  if (online) return null;
  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-2 bg-warning-soft px-4 py-2 text-sm font-medium text-warning"
    >
      <WifiOff className="size-4" aria-hidden="true" />
      <span>
        <strong className="font-semibold">{t('common.offline')}.</strong> {t('common.offlineBody')}
      </span>
    </div>
  );
}
