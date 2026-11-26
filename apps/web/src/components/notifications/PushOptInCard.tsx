import { BellRing, BellOff } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { useBrowserPush } from '@/features/notifications/push';

/** Ask only from a clear, customer-initiated action — never on page load. */
export function PushOptInCard() {
  const push = useBrowserPush();

  if (!push.supported) {
    return (
      <div className="mb-4 rounded-xl border border-border bg-muted/40 p-3">
        <p className="flex items-center gap-2 text-sm font-semibold">
          <BellRing className="size-4" aria-hidden="true" /> Notifications on this device
        </p>
        <p className="mt-1 text-sm text-muted-foreground">
          This browser cannot show push notifications. Order updates will still appear in the bell
          here.
        </p>
      </div>
    );
  }

  return (
    <section
      aria-label="Browser notifications"
      className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border bg-card p-3"
    >
      <div className="min-w-0">
        <p className="flex items-center gap-2 text-sm font-semibold">
          {push.enabled ? (
            <BellRing className="size-4 text-primary" aria-hidden="true" />
          ) : (
            <BellOff className="size-4 text-muted-foreground" aria-hidden="true" />
          )}
          {push.enabled ? 'Browser notifications are on' : 'Get order updates on this device'}
        </p>
        <p className="mt-1 text-xs text-muted-foreground">
          {push.enabled
            ? 'Offers and important shop updates can reach you when the app is closed.'
            : push.permission === 'denied'
              ? 'Notifications are blocked in browser settings. Allow them there, then come back.'
              : push.publicKeyConfigured
                ? 'Optional. We ask the browser only after you tap the button.'
                : 'Push is not configured for the shop yet. In-app notifications still work.'}
        </p>
        {push.error && (
          <p role="alert" className="mt-1 text-xs font-medium text-destructive">
            {push.error}
          </p>
        )}
      </div>
      {push.ready && (push.publicKeyConfigured || push.enabled) && (
        <Button
          variant={push.enabled ? 'outline' : 'primary'}
          size="sm"
          disabled={push.isPending || (push.permission === 'denied' && !push.enabled)}
          onClick={push.enabled ? push.disable : push.enable}
        >
          {push.isPending ? 'Saving…' : push.enabled ? 'Turn off' : 'Turn on'}
        </Button>
      )}
    </section>
  );
}
