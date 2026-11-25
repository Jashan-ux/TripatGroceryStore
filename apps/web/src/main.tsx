import { QueryClientProvider } from '@tanstack/react-query';
import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import { Toaster } from 'sonner';

import App from '@/App';
import { ErrorBoundary } from '@/components/common/ErrorBoundary';
import { queryClient } from '@/lib/queryClient';
import { registerServiceWorker } from '@/lib/serviceWorker';
import '@/styles/globals.css';

const container = document.getElementById('root');
if (!container) throw new Error('Root element #root is missing from index.html');

createRoot(container).render(
  <StrictMode>
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <App />
        </BrowserRouter>
        <Toaster
          position="top-center"
          richColors
          closeButton
          toastOptions={{ className: 'rounded-xl text-sm' }}
        />
      </QueryClientProvider>
    </ErrorBoundary>
  </StrictMode>,
);

registerServiceWorker();
