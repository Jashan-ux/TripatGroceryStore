import type { OfferIn } from '@tripat/api-client';
import { Megaphone, Send } from 'lucide-react';
import { useState } from 'react';

import { useAdminOffers, useCurrentOfferAdmin, useSendOffer } from '@/admin/adminCatalogue';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { Textarea } from '@/components/ui/textarea';
import { usePageTitle } from '@/hooks/usePageTitle';
import { formatIst } from '@/lib/utils';

const AUDIENCES: { value: OfferIn['audience']; label: string }[] = [
  { value: 'all', label: 'Every customer' },
  { value: 'gold', label: 'Gold members' },
  { value: 'platinum', label: 'Platinum members' },
  { value: 'diamond', label: 'Diamond members' },
];

/**
 * Offers.
 *
 * "Sent" here means three concrete things: a row in every matching customer's
 * bell, an email in the outbox, and a banner on the storefront until it expires.
 * The history shows the counts that actually happened, so the owner can see
 * whether "everyone" was forty people or four hundred.
 */
export function AdminOffersPage() {
  usePageTitle(undefined, 'Offers · Admin');
  const [page, setPage] = useState(1);
  const history = useAdminOffers(page);
  const current = useCurrentOfferAdmin();
  const send = useSendOffer();

  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [href, setHref] = useState('/');
  const [audience, setAudience] = useState<OfferIn['audience']>('all');
  const [days, setDays] = useState('7');
  const [notice, setNotice] = useState<string | null>(null);

  const sendOffer = () => {
    setNotice(null);
    const expiryDays = Number(days);
    send.mutate(
      {
        title: title.trim(),
        body: body.trim(),
        href: href.trim() || '/',
        audience,
        expires_at:
          expiryDays > 0 ? new Date(Date.now() + expiryDays * 86_400_000).toISOString() : null,
      },
      {
        onSuccess: (offer) => {
          setNotice(
            `Sent to ${offer.recipients} customer${offer.recipients === 1 ? '' : 's'} — ` +
              `${offer.emails_queued} email${offer.emails_queued === 1 ? '' : 's'} queued · ` +
              `${offer.push_queued} push device${offer.push_queued === 1 ? '' : 's'} targeted.`,
          );
          setTitle('');
          setBody('');
        },
      },
    );
  };

  return (
    <div className="container max-w-3xl space-y-4 py-5 pb-nav-safe md:pb-8">
      <h1 className="text-xl font-extrabold tracking-tight">Offers</h1>

      {current.data?.offer && (
        <p className="rounded-lg bg-info-soft p-2.5 text-sm text-info">
          On the storefront now: <strong>{current.data.offer.title}</strong>
          {current.data.offer.expires_at
            ? ` until ${formatIst(current.data.offer.expires_at)}`
            : ' until you replace it'}
        </p>
      )}

      <section className="space-y-2 rounded-xl border border-border bg-card p-3">
        <h2 className="flex items-center gap-1.5 text-sm font-bold">
          <Megaphone className="size-4 text-primary" aria-hidden="true" /> New offer
        </h2>
        <label className="block text-xs font-semibold" htmlFor="title">
          Title
          <Input
            id="title"
            className="mt-1"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            maxLength={140}
            placeholder="Diwali week: 10% off dry fruits"
          />
        </label>
        <label className="block text-xs font-semibold" htmlFor="details">
          Details
          <Textarea
            id="details"
            className="mt-1"
            rows={3}
            value={body}
            onChange={(event) => setBody(event.target.value)}
            maxLength={1000}
            placeholder="On all 500 g and 1 kg packs, till Sunday."
          />
        </label>
        <div className="grid gap-2 sm:grid-cols-3">
          <label className="text-xs font-semibold" htmlFor="who-hears-it">
            Who hears it
            <Select
              id="who-hears-it"
              className="mt-1"
              value={audience}
              onChange={(event) => setAudience(event.target.value as OfferIn['audience'])}
            >
              {AUDIENCES.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </label>
          <label className="text-xs font-semibold" htmlFor="link-inside-the-app">
            Link inside the app
            <Input
              id="link-inside-the-app"
              className="mt-1"
              value={href}
              onChange={(event) => setHref(event.target.value)}
              placeholder="/search?q=dry fruits"
            />
          </label>
          <label className="text-xs font-semibold" htmlFor="stops-showing-after-days">
            Stops showing after (days)
            <Input
              id="stops-showing-after-days"
              className="mt-1"
              inputMode="numeric"
              value={days}
              onChange={(event) => setDays(event.target.value.replace(/\D/g, ''))}
            />
          </label>
        </div>

        {notice && (
          <p
            role="status"
            className="rounded-lg bg-success-soft p-2.5 text-sm font-medium text-success"
          >
            {notice}
          </p>
        )}
        {send.isError && (
          <p
            role="alert"
            className="rounded-lg bg-warning-soft p-2.5 text-sm font-medium text-warning"
          >
            {send.error.message}
          </p>
        )}

        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={sendOffer} disabled={send.isPending || title.trim().length < 3}>
            <Send aria-hidden="true" /> {send.isPending ? 'Sending…' : 'Send offer'}
          </Button>
          <p className="text-xs text-muted-foreground">
            It reaches the bell and storefront banner. Opted-in browsers are targeted for push when
            push is configured; the count is not a delivery receipt.
          </p>
        </div>
      </section>

      <section className="space-y-2">
        <h2 className="text-sm font-bold">What has been sent</h2>
        {history.isPending ? (
          <Skeleton className="h-40 w-full rounded-xl" />
        ) : (history.data?.items ?? []).length === 0 ? (
          <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
            Nothing yet. The first offer you send appears here.
          </p>
        ) : (
          <ul className="space-y-2">
            {(history.data?.items ?? []).map((offer) => (
              <li key={offer.id} className="rounded-xl border border-border bg-card p-3">
                <div className="flex flex-wrap items-baseline justify-between gap-1">
                  <p className="font-semibold">{offer.title}</p>
                  <p className="text-xs text-muted-foreground">{formatIst(offer.sent_at)}</p>
                </div>
                {offer.body && <p className="mt-0.5 text-sm text-muted-foreground">{offer.body}</p>}
                <p className="mt-1 text-xs">
                  <span className="font-semibold">{offer.recipients}</span> bell
                  {offer.recipients === 1 ? '' : 's'} ·{' '}
                  <span className="font-semibold">{offer.emails_queued}</span> email
                  {offer.emails_queued === 1 ? '' : 's'} ·{' '}
                  <span className="font-semibold">{offer.push_queued}</span> push targeted ·{' '}
                  {AUDIENCES.find((option) => option.value === offer.audience)?.label ??
                    offer.audience}
                </p>
              </li>
            ))}
          </ul>
        )}
        {history.data && history.data.total_pages > 1 && (
          <div className="flex items-center justify-center gap-2">
            <Button
              variant="outline"
              size="sm"
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
            >
              Previous
            </Button>
            <p className="text-xs text-muted-foreground">
              Page {history.data.page} of {history.data.total_pages}
            </p>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= history.data.total_pages}
              onClick={() => setPage(page + 1)}
            >
              Next
            </Button>
          </div>
        )}
      </section>
    </div>
  );
}
