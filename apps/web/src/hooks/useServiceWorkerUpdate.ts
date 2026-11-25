import { useEffect, useState } from 'react';

import { UPDATE_READY_EVENT } from '@/lib/serviceWorker';

/** True once a new deploy is installed and waiting to activate. */
export function useServiceWorkerUpdate(): { updateReady: boolean; dismiss: () => void } {
  const [updateReady, setUpdateReady] = useState(false);
  const [dismissed, setDismissed] = useState(false);

  useEffect(() => {
    const handler = () => setUpdateReady(true);
    window.addEventListener(UPDATE_READY_EVENT, handler);
    return () => window.removeEventListener(UPDATE_READY_EVENT, handler);
  }, []);

  return {
    updateReady: updateReady && !dismissed,
    dismiss: () => setDismissed(true),
  };
}
