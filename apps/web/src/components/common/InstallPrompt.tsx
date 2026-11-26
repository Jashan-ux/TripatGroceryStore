import { Download, X } from 'lucide-react';
import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';

interface InstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>;
}

function isStandalone(): boolean {
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  );
}

function isAppleMobile(): boolean {
  return (
    /iPhone|iPad|iPod/i.test(navigator.userAgent) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  );
}

/**
 * A polite install nudge, never a modal and never a surprise permission prompt.
 * Chromium supplies a real install event. On iOS the copy explains the manual
 * Share → Add to Home Screen path, since Safari has no install event.
 */
export function InstallPrompt() {
  const [event, setEvent] = useState<InstallPromptEvent | null>(null);
  const [dismissed, setDismissed] = useState(false);
  const [installed, setInstalled] = useState(isStandalone);
  const appleMobile = isAppleMobile();

  useEffect(() => {
    const onBeforeInstall = (raw: Event) => {
      raw.preventDefault();
      setEvent(raw as InstallPromptEvent);
    };
    const onInstalled = () => {
      setInstalled(true);
      setEvent(null);
    };
    window.addEventListener('beforeinstallprompt', onBeforeInstall);
    window.addEventListener('appinstalled', onInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', onBeforeInstall);
      window.removeEventListener('appinstalled', onInstalled);
    };
  }, []);

  if (installed || dismissed || (!event && !appleMobile) || isStandalone()) return null;

  return (
    <aside
      aria-label="Install Tripat Pansari"
      className="border-b border-primary-200 bg-primary-50 px-4 py-2 text-foreground"
    >
      <div className="container flex flex-wrap items-center justify-between gap-2">
        <p className="flex min-w-0 items-start gap-2 text-sm">
          <Download className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
          <span>
            <strong className="font-semibold">Keep the shop close.</strong>{' '}
            {appleMobile
              ? 'Tap Share, then “Add to Home Screen” to install.'
              : 'Install the app for a quicker way back to your shop.'}
          </span>
        </p>
        <div className="flex items-center gap-1">
          {event && (
            <Button
              size="sm"
              onClick={() => {
                void (async () => {
                  await event.prompt();
                  const choice = await event.userChoice;
                  if (choice.outcome === 'accepted') setInstalled(true);
                  setEvent(null);
                })();
              }}
            >
              Install
            </Button>
          )}
          <Button
            size="icon"
            variant="ghost"
            aria-label="Dismiss install suggestion"
            onClick={() => setDismissed(true)}
          >
            <X aria-hidden="true" />
          </Button>
        </div>
      </div>
    </aside>
  );
}
