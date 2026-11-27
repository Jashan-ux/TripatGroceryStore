/// <reference lib="webworker" />
/**
 * The storefront service worker: an offline shelf, never an offline till.
 *
 * Only public GET catalogue data is cached (categories, home, brands, product
 * lists/details). Customer-specific `/api/*`, order placement, wallets, admin,
 * auth, and Supabase are always network-only. A returning shopper can browse
 * what they have already opened; trying to place an order still needs the server
 * to check live stock and price.
 */
import { CacheableResponsePlugin } from 'workbox-cacheable-response';
import { clientsClaim } from 'workbox-core';
import { ExpirationPlugin } from 'workbox-expiration';
import {
  cleanupOutdatedCaches,
  createHandlerBoundToURL,
  precacheAndRoute,
} from 'workbox-precaching';
import { NavigationRoute, registerRoute } from 'workbox-routing';
import { NetworkFirst, NetworkOnly, StaleWhileRevalidate } from 'workbox-strategies';

interface PushMessage {
  title?: string;
  body?: string;
  href?: string;
}

function parsePushMessage(value: unknown): PushMessage {
  if (typeof value !== 'object' || value === null) return {};
  const record = value as Record<string, unknown>;
  return {
    ...(typeof record.title === 'string' ? { title: record.title } : {}),
    ...(typeof record.body === 'string' ? { body: record.body } : {}),
    ...(typeof record.href === 'string' ? { href: record.href } : {}),
  };
}

declare global {
  // Vite's app tsconfig includes DOM types, so `self` is modeled as Window in
  // this source even though Vite compiles it into a dedicated worker bundle.
  interface Window {
    __WB_MANIFEST: Array<{ url: string; revision?: string | null }>;
  }
}

const worker = self as unknown as ServiceWorkerGlobalScope;

precacheAndRoute(self.__WB_MANIFEST);
cleanupOutdatedCaches();
clientsClaim();

// The app shows a consent prompt before sending this message. Do not skip
// waiting automatically; only activate a new release after the shopper accepts.
worker.addEventListener('message', (event: ExtendableMessageEvent) => {
  const message = event.data as { type?: unknown } | null;
  if (message?.type === 'SKIP_WAITING') event.waitUntil(worker.skipWaiting());
});

// Navigation falls back to the precached app shell. The admin stays online-only
// and all API paths are excluded; it is operational tooling, not an offline page.
registerRoute(
  new NavigationRoute(createHandlerBoundToURL('/index.html'), {
    denylist: [/^\/api\//, /^\/admin(?:\/|$)/],
  }),
);

const isPublicCatalogue = (url: URL): boolean => {
  if (/^\/api\/v1\/(?:categories(?:\/[^/]+)?|brands)\/?$/.test(url.pathname)) return true;
  if (url.pathname === '/api/v1/home') return true;
  return /^\/api\/v1\/products(?:\/[^/]+)?\/?$/.test(url.pathname);
};

// Network-first is important here: stock and prices should be fresh when online;
// cache is only the honest, browsed-before fallback when the connection is gone.
registerRoute(
  ({ url, request }) => request.method === 'GET' && isPublicCatalogue(url),
  new NetworkFirst({
    cacheName: 'public-catalogue-v1',
    networkTimeoutSeconds: 3,
    plugins: [
      new CacheableResponsePlugin({ statuses: [200] }),
      new ExpirationPlugin({ maxEntries: 180, maxAgeSeconds: 60 * 60 * 24 * 14 }),
    ],
  }),
);

// Every other API request stays out of caches — notably checkout, orders,
// customer records, push subscriptions, the notification bell and every admin API.
registerRoute(({ url }) => url.pathname.startsWith('/api/'), new NetworkOnly());
registerRoute(({ url }) => url.hostname.endsWith('.supabase.co'), new NetworkOnly());

registerRoute(
  ({ url }) => url.hostname.endsWith('tile.openstreetmap.org'),
  new StaleWhileRevalidate({
    cacheName: 'osm-tiles',
    plugins: [
      new CacheableResponsePlugin({ statuses: [0, 200] }),
      new ExpirationPlugin({ maxEntries: 300, maxAgeSeconds: 60 * 60 * 24 * 14 }),
    ],
  }),
);
registerRoute(
  ({ request }) => request.destination === 'image',
  new StaleWhileRevalidate({
    cacheName: 'catalog-images',
    plugins: [new ExpirationPlugin({ maxEntries: 200, maxAgeSeconds: 60 * 60 * 24 * 30 })],
  }),
);

worker.addEventListener('push', (event: PushEvent) => {
  let message: PushMessage = {};
  try {
    message = parsePushMessage(event.data?.json());
  } catch {
    message = { title: 'Tripat Pansari', body: event.data?.text() ?? '' };
  }
  const title = message.title?.trim() || 'Tripat Pansari · MSG Store';
  const href = message.href?.startsWith('/') && !message.href.startsWith('//') ? message.href : '/';
  event.waitUntil(
    worker.registration.showNotification(title, {
      body: message.body ?? '',
      icon: '/icons/icon-192.png',
      badge: '/icons/icon-96.png',
      data: { href },
      tag: 'tripat-offer',
    }),
  );
});

worker.addEventListener('notificationclick', (event: NotificationEvent) => {
  event.notification.close();
  const notificationData = event.notification.data as { href?: unknown } | null;
  const requested = notificationData?.href;
  const target =
    typeof requested === 'string' && requested.startsWith('/') && !requested.startsWith('//')
      ? requested
      : '/';
  event.waitUntil(
    worker.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(async (windows) => {
      for (const client of windows) {
        if ('focus' in client) {
          await client.focus();
          if ('navigate' in client) await client.navigate(target);
          return;
        }
      }
      await worker.clients.openWindow(target);
    }),
  );
});
