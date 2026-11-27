import { AlertTriangle } from 'lucide-react';
import { Component, type ErrorInfo, type ReactNode } from 'react';

import { Button } from '@/components/ui/button';
import { t } from '@/i18n';

interface Props {
  children: ReactNode;
}
interface State {
  hasError: boolean;
}

/**
 * Last-resort boundary: a render error must never leave a blank white page on a
 * customer's phone. Errors are logged without PII.
 */
export class ErrorBoundary extends Component<Props, State> {
  override state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('render_error', { message: error.message, componentStack: info.componentStack });
  }

  override render(): ReactNode {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center gap-4 px-4 text-center">
        <AlertTriangle className="size-10 text-primary" aria-hidden="true" />
        <h1 className="text-xl font-bold">{t('common.somethingWrong')}</h1>
        <p className="text-sm text-muted-foreground">{t('common.somethingWrongBody')}</p>
        <Button onClick={() => window.location.reload()}>{t('common.reload')}</Button>
      </div>
    );
  }
}
