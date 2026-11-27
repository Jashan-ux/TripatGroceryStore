import { CalendarClock } from 'lucide-react';
import type { ReactNode } from 'react';

import { CallStoreButton } from '@/components/common/CallStoreButton';
import { EmptyState } from '@/components/common/EmptyState';
import { usePageTitle } from '@/hooks/usePageTitle';
import { t } from '@/i18n';

interface Props {
  titleKey?: string;
  body?: ReactNode;
}

/**
 * Honest placeholder for sections that ship in a later phase. It is a real,
 * useful page (with a way to order by phone), not a dead link.
 */
export default function ComingSoonPage({ titleKey, body }: Props) {
  usePageTitle(titleKey);
  return (
    <div className="container py-6">
      {titleKey ? <h1 className="mb-4 text-xl font-bold">{t(titleKey)}</h1> : null}
      <EmptyState
        icon={CalendarClock}
        title={t('common.comingSoonTitle')}
        body={t('common.comingSoonBody')}
        action={<CallStoreButton className="mt-2" />}
      />
      {body ? <div className="mt-4 text-sm text-muted-foreground">{body}</div> : null}
    </div>
  );
}
