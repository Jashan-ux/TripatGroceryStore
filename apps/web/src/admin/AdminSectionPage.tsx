import { Construction } from 'lucide-react';

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { usePageTitle } from '@/hooks/usePageTitle';
import { t } from '@/i18n';

interface Props {
  titleKey: string;
  summary: string;
  bullets: readonly string[];
}

/**
 * Section landing inside the admin bundle. Each phase replaces one of these
 * with the real tool (orders in Phase 3, catalogue tools in Phase 5, analytics
 * in Phase 6); until then the page states exactly what is coming rather than
 * faking data.
 */
export function AdminSectionPage({ titleKey, summary, bullets }: Props) {
  usePageTitle(titleKey);
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold">{t(titleKey)}</h1>
        <p className="text-sm text-muted-foreground">{summary}</p>
      </div>
      <Card>
        <CardHeader className="flex-row items-center gap-2">
          <Construction className="size-4 text-primary" aria-hidden="true" />
          <CardTitle>{t('admin.buildNote')}</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="list-disc space-y-1 pl-5 text-sm text-muted-foreground">
            {bullets.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}
