import { PhoneCall } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { useAuth } from '@/features/auth/useAuth';

const DISMISS_KEY = 'msg-store:phone-prompt-dismissed';

/**
 * C‑06: ask a signed-in customer for a mobile number the first time they are
 * missing one. The number is what the delivery partner calls, so the prompt is
 * shown once per session and can be dismissed — never blocking checkout later
 * (checkout has its own hard requirement).
 */
export function PhonePrompt() {
  const { status, needsPhone } = useAuth();
  const navigate = useNavigate();
  const [dismissed, setDismissed] = useState(() =>
    typeof sessionStorage === 'undefined' ? false : sessionStorage.getItem(DISMISS_KEY) === '1',
  );
  const [open, setOpen] = useState(false);

  useEffect(() => {
    setOpen(status === 'authenticated' && needsPhone && !dismissed);
  }, [status, needsPhone, dismissed]);

  const dismiss = () => {
    sessionStorage.setItem(DISMISS_KEY, '1');
    setDismissed(true);
    setOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={(next) => (next ? setOpen(true) : dismiss())}>
      <DialogContent>
        <PhoneCall className="mb-2 size-8 text-primary" aria-hidden="true" />
        <DialogTitle>Add your mobile number</DialogTitle>
        <DialogDescription>
          Our delivery partner calls before arriving. Adding a number now means a faster handover on
          your first order.
        </DialogDescription>
        <div className="mt-4 flex flex-col gap-2 sm:flex-row">
          <Button
            className="sm:flex-1"
            onClick={() => {
              setOpen(false);
              navigate('/profile#phone');
            }}
          >
            Add number
          </Button>
          <Button variant="ghost" className="sm:flex-1" onClick={dismiss}>
            Later
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
