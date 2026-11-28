import { Badge } from '@/components/ui/badge';
import { t } from '@/i18n';

/**
 * Status → human label + tone, in one place. Any status the API adds later
 * still renders (title-cased), rather than breaking the page.
 */
const COPY: Record<
  string,
  { key: string; tone: 'brand' | 'success' | 'warning' | 'danger' | 'neutral' | 'info' }
> = {
  processing: { key: 'processing', tone: 'info' },
  accepted: { key: 'accepted', tone: 'brand' },
  packing: { key: 'packing', tone: 'info' },
  shipped: { key: 'shipped', tone: 'brand' },
  out_for_delivery: { key: 'outForDelivery', tone: 'brand' },
  delivered: { key: 'delivered', tone: 'success' },
  cancelled: { key: 'cancelled', tone: 'neutral' },
  returned: { key: 'returned', tone: 'warning' },
};

export function OrderStatusBadge({ status }: { status: string }) {
  const copy = COPY[status];
  return (
    <Badge tone={copy?.tone ?? 'neutral'}>
      {copy ? t(`status.${copy.key}`) : status.replace(/_/g, ' ')}
    </Badge>
  );
}
