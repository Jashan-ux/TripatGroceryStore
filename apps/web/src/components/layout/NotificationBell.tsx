import { Bell } from 'lucide-react';
import { Link } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { useUnreadCount } from '@/features/notifications/queries';
import { t } from '@/i18n';

/**
 * Header bell with a red dot.
 *
 * The count is server truth (unread notifications), not a local flag, so it is
 * right after a reload, on a second device, and after the shop moves an order.
 */
export function NotificationBell() {
  const unread = useUnreadCount();
  const count = unread.data?.unread_count ?? 0;

  return (
    <Button
      asChild
      variant="ghost"
      size="icon"
      aria-label={count > 0 ? `${t('nav.notifications')}, ${count} unread` : t('nav.notifications')}
      className="relative"
    >
      <Link to="/notifications">
        <Bell aria-hidden="true" />
        {count > 0 && (
          <span
            aria-hidden="true"
            className="absolute right-1.5 top-1.5 min-w-4 rounded-full bg-destructive px-1 text-center text-[10px] font-bold leading-4 text-destructive-foreground"
          >
            {count > 99 ? '99+' : count}
          </span>
        )}
      </Link>
    </Button>
  );
}
