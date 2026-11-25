import { RefreshCw } from 'lucide-react';

import { useServiceWorkerUpdate } from '@/hooks/useServiceWorkerUpdate';
import { t } from '@/i18n';
import { applyUpdate } from '@/lib/serviceWorker';

/**
 * Slide-down notice when a new deploy is installed. The user decides when to
 * reload — the app never swaps itself out mid-order.
 */
export function UpdatePrompt() {
  const { updateReady, dismiss } = useServiceWorkerUpdate();
  if (!updateReady) return null;
  return (
    <div
      role="status"
      aria-live="polite"
      className="animate-slide-down border-b border-border bg-foreground px-4 py-2 text-background"
    >
      <div className="container flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-medium">{t('common.updateAvailable')}</p>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => {
              dismiss();
              applyUpdate();
            }}
            className="inline-flex min-h-touch items-center gap-1.5 rounded-lg bg-primary px-3 text-sm font-semibold text-primary-foreground"
          >
            <RefreshCw className="size-4" aria-hidden="true" />
            {t('common.updateAction')}
          </button>
          <button
            type="button"
            onClick={dismiss}
            className="min-h-touch rounded-lg px-3 text-sm font-medium underline-offset-4 hover:underline"
          >
            {t('common.later')}
          </button>
        </div>
      </div>
    </div>
  );
}
