import type { FeedbackIn } from '@tripat/api-client';
import { Clock, Mail, MapPin, Phone, Send } from 'lucide-react';
import { useState, type FormEvent } from 'react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { useSendFeedback } from '@/features/feedback/queries';
import { usePageTitle } from '@/hooks/usePageTitle';
import { useStoreConfig } from '@/hooks/useStoreConfig';
import { t } from '@/i18n';
import { toTelHref } from '@/lib/utils';

/**
 * The contact page: how to reach the shop, and a way to write to it.
 *
 * The phone number is a real `tel:` link and the address links to Maps — on a
 * phone those two are the whole page for most customers. The form is the slow
 * path for people who cannot talk right now; it lands in the owner's admin inbox
 * and in the shop's email, so a message is never lost to a mail client.
 */
export default function ContactPage() {
  usePageTitle('contact.title');
  const config = useStoreConfig();
  const send = useSendFeedback();

  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [email, setEmail] = useState('');
  const [kind, setKind] = useState<FeedbackIn['kind']>('general');
  const [message, setMessage] = useState('');
  const [sent, setSent] = useState(false);

  const store = config.data;

  const submit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSent(false);
    send.mutate(
      { name, phone, email, kind, message },
      {
        onSuccess: () => {
          setSent(true);
          setMessage('');
        },
      },
    );
  };

  return (
    <div className="container max-w-3xl space-y-6 py-5 pb-nav-safe md:pb-8">
      <div>
        <h1 className="text-xl font-extrabold tracking-tight">{t('contact.title')}</h1>
        <p className="mt-1 text-sm text-muted-foreground">{t('contact.subtitle')}</p>
      </div>

      <section
        aria-labelledby="store-details"
        className="min-h-[20rem] rounded-xl border border-border bg-card p-4 md:min-h-0"
      >
        <h2 id="store-details" className="text-base font-bold">
          {store?.store_name ?? t('brand.full')}
        </h2>
        <ul className="mt-3 space-y-2.5 text-sm">
          <li className="flex items-start gap-2.5">
            <Phone className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
            {store?.store_phone ? (
              <a href={toTelHref(store.store_phone)} className="font-semibold text-primary">
                {store.store_phone}
              </a>
            ) : (
              <span className="text-muted-foreground">{t('common.loading')}…</span>
            )}
          </li>
          <li className="flex items-start gap-2.5">
            <MapPin className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
            <span>{store?.store_address ?? '—'}</span>
          </li>
          <li className="flex items-start gap-2.5">
            <Clock className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
            <span>{t('contact.hours')}</span>
          </li>
          {store?.feedback_email && (
            <li className="flex items-start gap-2.5">
              <Mail className="mt-0.5 size-4 shrink-0 text-primary" aria-hidden="true" />
              <a href={`mailto:${store.feedback_email}`} className="break-all text-primary">
                {store.feedback_email}
              </a>
            </li>
          )}
        </ul>
        {store?.store_maps_url && (
          <Button asChild variant="outline" size="sm" className="mt-3">
            <a href={store.store_maps_url} target="_blank" rel="noopener noreferrer">
              <MapPin aria-hidden="true" /> {t('contact.openMaps')}
            </a>
          </Button>
        )}
      </section>

      <section
        aria-labelledby="write-to-us"
        className="rounded-xl border border-border bg-card p-4"
      >
        <h2 id="write-to-us" className="text-base font-bold">
          {t('contact.formTitle')}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">{t('contact.formBody')}</p>

        {sent && (
          <p
            role="status"
            className="mt-3 rounded-lg bg-success-soft p-3 text-sm font-medium text-success"
          >
            {t('contact.sent')}
          </p>
        )}

        <form className="mt-4 space-y-3" onSubmit={submit}>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="block text-sm font-semibold">
              {t('contact.name')}
              <Input
                className="mt-1"
                value={name}
                onChange={(event) => setName(event.target.value)}
                autoComplete="name"
                maxLength={120}
              />
            </label>
            <label className="block text-sm font-semibold">
              {t('contact.phone')}
              <Input
                className="mt-1"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                inputMode="tel"
                autoComplete="tel"
                maxLength={20}
              />
            </label>
          </div>
          <label className="block text-sm font-semibold">
            {t('contact.email')}
            <Input
              className="mt-1"
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              maxLength={320}
            />
          </label>
          <label className="block text-sm font-semibold">
            {t('contact.kind')}
            <Select
              className="mt-1"
              value={kind}
              onChange={(event) => setKind(event.target.value as FeedbackIn['kind'])}
            >
              <option value="general">{t('contact.kindGeneral')}</option>
              <option value="order">{t('contact.kindOrder')}</option>
              <option value="product">{t('contact.kindProduct')}</option>
              <option value="other">{t('contact.kindOther')}</option>
            </Select>
          </label>
          <label className="block text-sm font-semibold">
            {t('contact.message')}
            <Textarea
              className="mt-1"
              value={message}
              onChange={(event) => setMessage(event.target.value)}
              required
              minLength={5}
              maxLength={4000}
              placeholder={t('contact.messagePlaceholder')}
            />
          </label>

          {send.isError && (
            <p role="alert" className="rounded-lg bg-warning-soft p-3 text-sm text-warning">
              {send.error.message}
            </p>
          )}

          <Button type="submit" disabled={send.isPending} className="w-full sm:w-auto">
            <Send aria-hidden="true" />
            {send.isPending ? t('contact.sending') : t('contact.send')}
          </Button>
          <p className="text-xs text-muted-foreground">{t('contact.privacyNote')}</p>
        </form>
      </section>
    </div>
  );
}
