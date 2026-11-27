/**
 * The storefront offer banner.
 *
 * One offer is live at a time (the newest unexpired one). Dismissal is stored on
 * the device by offer id, so a customer who has read it is not shown it again —
 * and a *new* offer still appears, which is the whole point.
 */
import type { CurrentOfferOut } from '@tripat/api-client';
import { useQuery } from '@tanstack/react-query';
import { useCallback, useState } from 'react';

import { api } from '@/lib/api';

const DISMISS_KEY = 'msg.offer.dismissed';

function readDismissed(): string | null {
  try {
    return window.localStorage.getItem(DISMISS_KEY);
  } catch {
    return null;
  }
}

export function useCurrentOffer() {
  return useQuery<CurrentOfferOut>({
    queryKey: ['offers', 'current'],
    queryFn: ({ signal }) => api.get<CurrentOfferOut>('/api/v1/offers/current', { signal }),
    staleTime: 5 * 60 * 1000,
  });
}

export function useOfferBanner() {
  const query = useCurrentOffer();
  const [dismissed, setDismissed] = useState<string | null>(readDismissed);

  const dismiss = useCallback((offerId: string) => {
    setDismissed(offerId);
    try {
      window.localStorage.setItem(DISMISS_KEY, offerId);
    } catch {
      // Private mode without storage: dismissal lasts for this visit only.
    }
  }, []);

  const offer = query.data?.offer ?? null;
  return {
    offer: offer && offer.id !== dismissed ? offer : null,
    dismiss,
    isPending: query.isPending,
  };
}
