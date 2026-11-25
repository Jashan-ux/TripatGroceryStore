/**
 * Service-worker registration.
 *
 * `registerType: 'prompt'` in the Vite config means a new deploy waits for the
 * user: the app shows an "update available" toast and only reloads when the
 * user accepts. This is the fix for the "stale app after deploy" defect.
 */
import { Workbox } from 'workbox-window';

export const UPDATE_READY_EVENT = 'msg:update-ready';

let workbox: Workbox | null = null;

export function registerServiceWorker(): void {
  if (!('serviceWorker' in navigator)) return;
  if (import.meta.env.DEV) return;

  workbox = new Workbox('/sw.js');

  workbox.addEventListener('waiting', () => {
    window.dispatchEvent(new CustomEvent(UPDATE_READY_EVENT));
  });

  workbox.addEventListener('controlling', (event) => {
    if (event.isUpdate) window.location.reload();
  });

  void workbox.register().catch(() => {
    // Registration failures are non-fatal: the app still works online.
  });
}

/** Apply a waiting update: activate the waiting SW, then reload once it controls. */
export function applyUpdate(): void {
  if (!workbox) {
    window.location.reload();
    return;
  }
  workbox.addEventListener('controlling', () => window.location.reload());
  workbox.messageSkipWaiting();
}
