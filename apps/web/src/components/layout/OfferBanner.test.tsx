import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { OfferBanner } from '@/components/layout/OfferBanner';
import { renderWithProviders } from '@/test/render';

const offer = {
  id: 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  title: 'Diwali week: 10% off dry fruits',
  body: 'On all 500 g packs, till Sunday.',
  href: '/search?q=dry%20fruits',
  audience: 'all',
  is_active: true,
  expires_at: null,
  recipients: 12,
  emails_queued: 9,
  sent_at: '2026-11-25T05:00:00Z',
  created_at: '2026-11-25T05:00:00Z',
};

function mockOffer(current: typeof offer | null) {
  vi.stubGlobal(
    'fetch',
    vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes('/api/v1/offers/current')) {
        return new Response(JSON.stringify({ offer: current }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        });
      }
      return new Response(JSON.stringify({}), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }),
  );
}

describe('OfferBanner', () => {
  beforeEach(() => {
    vi.unstubAllGlobals();
    window.localStorage.clear();
  });

  it('shows the live offer and links inside the app', async () => {
    mockOffer(offer);
    renderWithProviders(<OfferBanner />);

    const link = await screen.findByRole('link', { name: offer.title });
    expect(link).toHaveAttribute('href', offer.href);
    expect(screen.getByText(offer.body)).toBeInTheDocument();
  });

  it('renders nothing when the shop has no live offer', async () => {
    mockOffer(null);
    const { container } = renderWithProviders(<OfferBanner />);
    // An offer-less shop renders no banner markup at all (no empty strip).
    await waitFor(() => expect(container).toBeEmptyDOMElement());
  });

  it('stays dismissed on the next visit, but a new offer still appears', async () => {
    mockOffer(offer);
    const user = userEvent.setup();
    const first = renderWithProviders(<OfferBanner />);

    await user.click(
      await screen.findByRole('button', { name: new RegExp(`dismiss offer: ${offer.title}`, 'i') }),
    );
    expect(screen.queryByText(offer.title)).not.toBeInTheDocument();
    expect(window.localStorage.getItem('msg.offer.dismissed')).toBe(offer.id);
    first.unmount();

    // Same offer, fresh visit: still hidden.
    const second = renderWithProviders(<OfferBanner />);
    await waitFor(() => expect(second.container).toBeEmptyDOMElement());

    // A newer offer is not suppressed by the old dismissal.
    mockOffer({
      ...offer,
      id: 'cccccccc-cccc-cccc-cccc-cccccccccccc',
      title: 'Sunday: fresh paneer',
    });
    renderWithProviders(<OfferBanner />);
    expect(await screen.findByText('Sunday: fresh paneer')).toBeInTheDocument();
  });
});
