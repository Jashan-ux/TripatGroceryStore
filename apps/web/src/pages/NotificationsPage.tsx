import { BellRing, CheckCheck, PackageCheck, ReceiptText, Truck, XCircle } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';

import { EmptyState } from '@/components/common/EmptyState';
import { PushOptInCard } from '@/components/notifications/PushOptInCard';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import type { NotificationOut } from '@tripat/api-client';
import {
  NOTIFICATIONS_PAGE_SIZE,
  useAckNotification,
  useNotifications,
  useReadAllNotifications,
} from '@/features/notifications/queries';
import { usePageTitle } from '@/hooks/usePageTitle';
import { cn, formatIst } from '@/lib/utils';
import { useState } from 'react';

import { useAuth } from '@/features/auth/useAuth';

const ICONS = {
  order_placed: ReceiptText,
  order_status: Truck,
  order_cancelled: XCircle,
  new_order: PackageCheck,
  system: BellRing,
} as const;

/**
 * The bell's page.
 *
 * Reading is a server fact: opening this page does not mark anything, tapping a
 * line marks that line, and "Mark all read" is one explicit action. Tapping a line
 * also follows its `href`, which the API wrote — the client never composes deep
 * links for other people's data.
 */
export default function NotificationsPage() {
  usePageTitle(undefined, 'Notifications');
  const navigate = useNavigate();
  const [page, setPage] = useState(1);
  const { status } = useAuth();
  const notifications = useNotifications(page);
  const ack = useAckNotification();
  const readAll = useReadAllNotifications();

  const data = notifications.data;

  const open = (entry: NotificationOut) => {
    if (!entry.read) ack.mutate(entry.id);
    if (entry.href) void navigate(entry.href);
  };

  // Defensive: the route is protected, but a page that renders a skeleton
  // forever for a signed-out visitor is a dead end if that gate ever changes.
  if (status === 'anonymous') {
    return (
      <div className="container max-w-2xl py-8">
        <EmptyState
          icon={BellRing}
          title="Sign in to see your notifications"
          body="Order updates — confirmed, shipped, delivered — arrive here."
          action={
            <Button asChild className="mt-2">
              <Link to="/sign-in?next=%2Fnotifications">Sign in</Link>
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="container max-w-2xl py-6 pb-nav-safe md:pb-8">
      <PushOptInCard />
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-extrabold tracking-tight">Notifications</h1>
          {data && data.unread_count > 0 && (
            <p className="text-sm text-muted-foreground">{data.unread_count} unread</p>
          )}
        </div>
        {data && data.unread_count > 0 && (
          <Button
            variant="outline"
            size="sm"
            disabled={readAll.isPending}
            onClick={() => readAll.mutate()}
          >
            <CheckCheck aria-hidden="true" />
            Mark all read
          </Button>
        )}
      </div>

      {notifications.isPending ? (
        <div className="space-y-2" role="status" aria-live="polite">
          <span className="sr-only">Loading notifications</span>
          {Array.from({ length: 4 }).map((_, index) => (
            <Skeleton key={index} className="h-20 w-full rounded-xl" />
          ))}
        </div>
      ) : notifications.isError ? (
        <EmptyState
          icon={BellRing}
          title="We could not load your notifications"
          body="Check your connection and try again."
          action={
            <Button className="mt-2" onClick={() => void notifications.refetch()}>
              Try again
            </Button>
          }
        />
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          icon={BellRing}
          title="Nothing here yet"
          body="We will tell you here when your order is confirmed, shipped and delivered."
          action={
            <Button asChild className="mt-2">
              <Link to="/orders">See your orders</Link>
            </Button>
          }
        />
      ) : (
        <>
          <ul className="space-y-2">
            {data.items.map((entry) => {
              const Icon = ICONS[entry.kind as keyof typeof ICONS] ?? BellRing;
              return (
                <li key={entry.id}>
                  <button
                    type="button"
                    onClick={() => open(entry)}
                    className={cn(
                      'flex w-full items-start gap-3 rounded-xl border p-3 text-left transition-colors',
                      entry.read
                        ? 'border-border bg-card hover:bg-secondary'
                        : 'border-primary-200 bg-primary-50/60 hover:bg-primary-50',
                    )}
                  >
                    <span
                      className={cn(
                        'mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-full',
                        entry.read
                          ? 'bg-muted text-muted-foreground'
                          : 'bg-primary text-primary-foreground',
                      )}
                    >
                      <Icon className="size-4" aria-hidden="true" />
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="flex items-start justify-between gap-2">
                        <span className={cn('text-sm', entry.read ? 'font-medium' : 'font-bold')}>
                          {entry.title}
                        </span>
                        {!entry.read && (
                          <span
                            className="mt-1 size-2 shrink-0 rounded-full bg-destructive"
                            aria-label="Unread"
                          />
                        )}
                      </span>
                      {entry.body && (
                        <span className="mt-0.5 block text-sm text-muted-foreground">
                          {entry.body}
                        </span>
                      )}
                      <span className="mt-1 block text-xs text-muted-foreground">
                        {formatIst(entry.created_at, {
                          day: 'numeric',
                          month: 'short',
                          hour: 'numeric',
                          minute: '2-digit',
                        })}
                      </span>
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>

          {data.total_pages > 1 && (
            <nav
              className="mt-4 flex items-center justify-between gap-3"
              aria-label="Notification pages"
            >
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((current) => current - 1)}
              >
                Newer
              </Button>
              <span className="text-xs text-muted-foreground">
                Page {data.page} of {data.total_pages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= data.total_pages}
                onClick={() => setPage((current) => current + 1)}
              >
                Older
              </Button>
            </nav>
          )}
          {data.total > NOTIFICATIONS_PAGE_SIZE && data.total_pages <= 1 && (
            <p className="mt-3 text-center text-xs text-muted-foreground">
              Showing the latest {data.items.length} notifications.
            </p>
          )}
        </>
      )}
    </div>
  );
}
