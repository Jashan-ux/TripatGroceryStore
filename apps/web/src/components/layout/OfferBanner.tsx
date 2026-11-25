import { Megaphone, X } from 'lucide-react';
import { Link } from 'react-router-dom';

import { useOfferBanner } from '@/features/offers/queries';

/**
 * The slide-down strip under the header. It is an `aria-live="polite"` region so
 * a screen reader announces a new offer once, and it is dismissible — a notice
 * that cannot be closed is an obstruction, not a message.
 */
export function OfferBanner() {
  const { offer, dismiss } = useOfferBanner();
  if (!offer) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="border-b border-primary-200 bg-primary-50 text-primary-900"
    >
      <div className="container flex items-start gap-2 py-2">
        <Megaphone className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <div className="min-w-0 flex-1 text-sm">
          <Link to={offer.href} className="font-bold underline-offset-2 hover:underline">
            {offer.title}
          </Link>
          {offer.body && (
            <p className="mt-0.5 line-clamp-2 text-xs text-primary-800">{offer.body}</p>
          )}
        </div>
        <button
          type="button"
          onClick={() => dismiss(offer.id)}
          aria-label={`Dismiss offer: ${offer.title}`}
          className="-m-1 shrink-0 rounded-lg p-1 text-primary-700 hover:bg-primary-100"
        >
          <X className="size-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
