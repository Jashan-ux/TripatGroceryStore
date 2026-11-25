/**
 * The bell.
 *
 * One query for the list, one for the red dot. The dot polls on a slow interval
 * (and only while the tab is visible) because a shop notification that arrives a
 * minute late is fine, while a request every two seconds on a phone battery is
 * not.
 */
import type {
  MarkAllReadOut,
  NotificationListOut,
  NotificationOut,
  UnreadCountOut,
} from '@tripat/api-client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { useAuth } from '@/features/auth/useAuth';
import { api } from '@/lib/api';

export const NOTIFICATIONS_PAGE_SIZE = 20;
const UNREAD_POLL_MS = 60 * 1000;

export function useNotifications(page = 1) {
  const { status } = useAuth();
  return useQuery<NotificationListOut>({
    queryKey: ['notifications', page],
    queryFn: ({ signal }) =>
      api.get<NotificationListOut>(
        `/api/v1/notifications?page=${page}&page_size=${NOTIFICATIONS_PAGE_SIZE}`,
        { signal },
      ),
    enabled: status === 'authenticated',
    staleTime: 30 * 1000,
  });
}

/** Just the number, for the red dot on the bell and the admin Orders tab. */
export function useUnreadCount() {
  const { status } = useAuth();
  return useQuery<UnreadCountOut>({
    queryKey: ['notifications', 'unread'],
    queryFn: ({ signal }) =>
      api.get<UnreadCountOut>('/api/v1/notifications/unread-count', { signal }),
    enabled: status === 'authenticated',
    staleTime: 30 * 1000,
    refetchInterval: UNREAD_POLL_MS,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  });
}

export function useAckNotification() {
  const queryClient = useQueryClient();
  return useMutation<NotificationOut, Error, string>({
    mutationFn: (id) => api.post<NotificationOut>(`/api/v1/notifications/${id}/ack`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
}

export function useReadAllNotifications() {
  const queryClient = useQueryClient();
  return useMutation<MarkAllReadOut, Error, void>({
    mutationFn: () => api.post<MarkAllReadOut>('/api/v1/notifications/read-all'),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
}
