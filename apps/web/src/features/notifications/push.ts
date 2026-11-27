/** Device-level web push opt-in. Permission is requested only from the user's tap. */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { useStoreConfig } from '@/hooks/useStoreConfig';
import { api } from '@/lib/api';

interface StoredSubscription {
  endpoint: string;
  keys: { p256dh: string; auth: string };
  expiration_time: string | null;
}

function browserSupportsPush(): boolean {
  return (
    typeof window !== 'undefined' &&
    window.isSecureContext &&
    'serviceWorker' in navigator &&
    'PushManager' in window &&
    'Notification' in window
  );
}

export function decodeApplicationServerKey(key: string): Uint8Array {
  const padding = '='.repeat((4 - (key.length % 4)) % 4);
  const base64 = (key + padding).replace(/-/g, '+').replace(/_/g, '/');
  const raw = window.atob(base64);
  return Uint8Array.from(raw, (character) => character.charCodeAt(0));
}

async function browserSubscription(): Promise<PushSubscription | null> {
  if (!browserSupportsPush()) return null;
  const registration = await navigator.serviceWorker.ready;
  return registration.pushManager.getSubscription();
}

function subscriptionPayload(subscription: PushSubscription): StoredSubscription {
  const json = subscription.toJSON();
  if (!json.endpoint || !json.keys?.p256dh || !json.keys.auth) {
    throw new Error('This browser returned an incomplete push subscription. Please try again.');
  }
  return {
    endpoint: json.endpoint,
    keys: { p256dh: json.keys.p256dh, auth: json.keys.auth },
    expiration_time:
      subscription.expirationTime === null
        ? null
        : new Date(subscription.expirationTime).toISOString(),
  };
}

export function useBrowserPush() {
  const queryClient = useQueryClient();
  const config = useStoreConfig();
  const supported = browserSupportsPush();
  const subscription = useQuery({
    queryKey: ['push', 'browser-subscription'],
    queryFn: browserSubscription,
    enabled: supported,
    staleTime: Infinity,
  });

  const enable = useMutation({
    mutationFn: async () => {
      if (!supported) throw new Error('Push notifications are not supported in this browser.');
      const publicKey = config.data?.vapid_public_key;
      if (!publicKey) throw new Error('Browser notifications are not configured by the shop yet.');
      if (Notification.permission === 'denied') {
        throw new Error('Notifications are blocked in your browser settings.');
      }
      const permission =
        Notification.permission === 'granted'
          ? Notification.permission
          : await Notification.requestPermission();
      if (permission !== 'granted') throw new Error('Allow notifications to turn them on here.');
      const registration = await navigator.serviceWorker.ready;
      const existing = await registration.pushManager.getSubscription();
      const active =
        existing ??
        (await registration.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: decodeApplicationServerKey(publicKey),
        }));
      await api.post('/api/v1/push/subscribe', subscriptionPayload(active));
      return active;
    },
    onSuccess: async (active) => {
      queryClient.setQueryData(['push', 'browser-subscription'], active);
      await queryClient.invalidateQueries({ queryKey: ['push', 'browser-subscription'] });
    },
  });

  const disable = useMutation({
    mutationFn: async () => {
      const active = await browserSubscription();
      if (!active) return;
      await api.delete('/api/v1/push/subscribe', { body: subscriptionPayload(active) });
      await active.unsubscribe();
    },
    onSuccess: async () => {
      queryClient.setQueryData(['push', 'browser-subscription'], null);
      await queryClient.invalidateQueries({ queryKey: ['push', 'browser-subscription'] });
    },
  });

  return {
    supported,
    permission: supported ? Notification.permission : 'unsupported',
    enabled: Boolean(subscription.data),
    ready: !supported || !subscription.isPending,
    publicKeyConfigured: Boolean(config.data?.vapid_public_key),
    isPending: enable.isPending || disable.isPending,
    error: enable.error?.message ?? disable.error?.message ?? null,
    enable: () => enable.mutate(),
    disable: () => disable.mutate(),
  };
}
