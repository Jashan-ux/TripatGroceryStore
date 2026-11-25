import { Badge } from '@/components/ui/badge';

/**
 * Status → human label + tone, in one place. Any status the API adds later
 * still renders (title-cased), rather than breaking the page.
 */
const COPY: Record<
  string,
  { label: string; tone: 'brand' | 'success' | 'warning' | 'danger' | 'neutral' | 'info' }
> = {
  processing: { label: 'Being packed', tone: 'info' },
  shipped: { label: 'On the way', tone: 'brand' },
  out_for_delivery: { label: 'Out for delivery', tone: 'brand' },
  delivered: { label: 'Delivered', tone: 'success' },
  cancelled: { label: 'Cancelled', tone: 'neutral' },
  returned: { label: 'Returned', tone: 'warning' },
};

export function OrderStatusBadge({ status }: { status: string }) {
  const copy = COPY[status] ?? {
    label: status.replace(/_/g, ' '),
    tone: 'neutral' as const,
  };
  return <Badge tone={copy.tone}>{copy.label}</Badge>;
}
