import { Compass } from 'lucide-react';
import { Link } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { usePageTitle } from '@/hooks/usePageTitle';
import { t } from '@/i18n';

export default function NotFoundPage() {
  usePageTitle('common.notFoundTitle');
  return (
    <div className="container flex min-h-[50vh] flex-col items-center justify-center gap-4 py-10 text-center">
      <Compass className="size-10 text-primary" aria-hidden="true" />
      <h1 className="text-2xl font-bold">{t('common.notFoundTitle')}</h1>
      <p className="max-w-sm text-sm text-muted-foreground">{t('common.notFoundBody')}</p>
      <Button asChild size="lg">
        <Link to="/">{t('common.backHome')}</Link>
      </Button>
    </div>
  );
}
