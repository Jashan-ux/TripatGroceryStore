import type { AddressIn, AddressOut, ProfileOut } from '@tripat/api-client';
import { AlertTriangle, CheckCircle2, MapPin, Phone, Plus, ShoppingBag, Truck } from 'lucide-react';
import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';

import { AddressForm } from '@/components/orders/AddressForm';
import { OrderTotals } from '@/components/orders/OrderTotals';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { EmptyState } from '@/components/common/EmptyState';
import { useAuth } from '@/features/auth/useAuth';
import { useCart } from '@/features/cart/useCart';
import {
  toQuoteItems,
  useAddresses,
  useDeleteAddress,
  usePlaceOrder,
  useQuote,
  useSaveAddress,
} from '@/features/orders/queries';
import { usePageTitle } from '@/hooks/usePageTitle';
import { ApiError, api } from '@/lib/api';
import { cn, formatPaise } from '@/lib/utils';
import { getCurrentLanguage, t } from '@/i18n';
import { apiErrorMessage, blockingIssueMessage } from '@/i18n/messages';

/**
 * Ask the quote to use no more than this: the server clamps to the balance *and*
 * to what is payable, so one request answers "is there wallet money here?" and
 * "what would it cover?" without a second endpoint.
 */
const MAX_WALLET_ASK = 1_00_00_000;

/**
 * Checkout.
 *
 * Order of operations mirrors the API: pick an address → quote that pincode →
 * place the order with an `Idempotency-Key`. The key is derived from the payload
 * (address + basket), so a double tap or a retry after a dropped connection
 * replays the first order instead of creating a second one, while any real
 * change produces a new key.
 */
export default function CheckoutPage() {
  usePageTitle(undefined, t('checkout.title'));
  const cart = useCart();
  const navigate = useNavigate();
  const { profile, refreshProfile } = useAuth();

  const addresses = useAddresses();
  const saveAddress = useSaveAddress();
  const deleteAddress = useDeleteAddress();
  const placeOrder = usePlaceOrder();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<AddressOut | null>(null);
  const [note, setNote] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const [addressFieldErrors, setAddressFieldErrors] = useState<Record<string, string>>({});
  const [phoneDraft, setPhoneDraft] = useState('');
  const [orderError, setOrderError] = useState<ApiError | null>(null);
  const [useWallet, setUseWallet] = useState(false);

  const savedAddresses = addresses.data ?? [];
  const selected =
    savedAddresses.find((address) => address.id === selectedId) ??
    savedAddresses.find((address) => address.is_default) ??
    savedAddresses[0] ??
    null;

  const items = useMemo(() => toQuoteItems(cart.lines), [cart.lines]);
  // One key per attempt: a double tap or a reconnect retry replays the first
  // order instead of charging for a second one.
  const [idempotencyKey, setIdempotencyKey] = useState(() => crypto.randomUUID());
  // The payload can change while this page is open — a different address, or the
  // wallet switched on — so each of those starts a new attempt with a fresh key.
  const newAttempt = () => setIdempotencyKey(crypto.randomUUID());
  const chooseAddress = (id: string | null) => {
    setSelectedId(id);
    newAttempt();
  };

  // Ask for the wallet *first* (with a big number the server clamps), because the
  // balance decides whether the switch is even offered.
  const preview = useQuote(items, selected?.pincode, MAX_WALLET_ASK);
  const balance = preview.data?.wallet_available_paise ?? 0;
  const walletAsk = useWallet ? balance : 0;
  const quote = useQuote(items, selected?.pincode, walletAsk);

  const savePhone = useMutation<ProfileOut, ApiError, string>({
    mutationFn: (phone) => api.post<ProfileOut>('/api/v1/me/phone', { phone }),
    onSuccess: async () => {
      setPhoneDraft('');
      await refreshProfile();
    },
  });

  if (cart.lines.length === 0) {
    return (
      <div className="container py-8">
        <h1 className="mb-4 text-xl font-extrabold tracking-tight">{t('checkout.title')}</h1>
        <EmptyState
          icon={ShoppingBag}
          title={t('checkout.emptyTitle')}
          body={t('checkout.emptyBody')}
          action={
            <Button asChild className="mt-2">
              <Link to="/categories">{t('checkout.browseShop')}</Link>
            </Button>
          }
        />
      </div>
    );
  }

  const canPlace =
    Boolean(selected) &&
    Boolean(profile?.phone) &&
    Boolean(quote.data?.can_checkout) &&
    !placeOrder.isPending;

  const submitAddress = async (values: AddressIn) => {
    setFormError(null);
    setAddressFieldErrors({});
    try {
      const address = await saveAddress.mutateAsync({
        ...values,
        ...(editing ? { id: editing.id } : {}),
      });
      chooseAddress(address.id);
      setFormOpen(false);
      setEditing(null);
    } catch (error) {
      if (error instanceof ApiError) {
        setFormError(apiErrorMessage(error));
        setAddressFieldErrors(error.fieldErrors);
      } else {
        setFormError(t('checkout.addressSaveError'));
      }
    }
  };

  const onPlaceOrder = () => {
    if (!selected) return;
    setOrderError(null);
    placeOrder.mutate(
      {
        addressId: selected.id,
        idempotencyKey,
        customerNote: note,
        items,
        useWalletPaise: useWallet ? balance : 0,
      },
      {
        onSuccess: (order) => {
          cart.clear();
          void navigate(`/orders/${order.id}?placed=1`, { replace: true });
        },
        onError: (error) =>
          setOrderError(
            error instanceof ApiError ? error : new ApiError(0, 'error', t('checkout.orderError')),
          ),
      },
    );
  };

  return (
    <div className="container py-6 pb-nav-safe md:pb-8">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-extrabold tracking-tight">{t('checkout.title')}</h1>
          <p className="text-sm text-muted-foreground">{t('checkout.cashNoDeliveryFee')}</p>
        </div>
        <Link to="/cart" className="text-sm font-semibold text-primary hover:underline">
          {t('checkout.editCart')}
        </Link>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_21rem]">
        <div className="space-y-4">
          {/* 1. Where it goes */}
          <section aria-labelledby="address-heading" className="space-y-3">
            <h2 id="address-heading" className="flex items-center gap-2 text-sm font-bold">
              <MapPin className="size-4 text-primary" aria-hidden="true" />
              {t('checkout.address')}
            </h2>

            {addresses.isError && !addresses.data ? (
              <div
                role="alert"
                className="rounded-xl border border-border bg-warning-soft p-3 text-sm"
              >
                <p className="font-semibold">{t('checkout.addressLoadError')}</p>
                <p className="mt-1">{t('checkout.addressLoadBody')}</p>
                <Button
                  className="mt-2"
                  variant="outline"
                  size="sm"
                  onClick={() => void addresses.refetch()}
                >
                  {t('checkout.tryAgain')}
                </Button>
              </div>
            ) : addresses.isPending ? (
              <Skeleton className="h-24 w-full rounded-xl" />
            ) : savedAddresses.length === 0 || formOpen ? (
              <AddressForm
                address={editing}
                submitting={saveAddress.isPending}
                serverError={formError}
                serverFieldErrors={addressFieldErrors}
                onSubmit={submitAddress}
                onCancel={
                  savedAddresses.length > 0
                    ? () => {
                        setFormOpen(false);
                        setEditing(null);
                        setFormError(null);
                      }
                    : undefined
                }
              />
            ) : (
              <>
                <ul className="space-y-2">
                  {savedAddresses.map((address) => {
                    const active = selected?.id === address.id;
                    return (
                      <li key={address.id}>
                        <div
                          className={cn(
                            'rounded-xl border bg-card p-3 transition-colors',
                            active ? 'border-primary ring-1 ring-primary' : 'border-border',
                          )}
                        >
                          <div className="flex items-start gap-3">
                            <input
                              id={`address-${address.id}`}
                              type="radio"
                              name="address"
                              className="mt-1 size-4 accent-primary"
                              checked={active}
                              onChange={() => chooseAddress(address.id)}
                            />
                            <label
                              htmlFor={`address-${address.id}`}
                              className="min-w-0 flex-1 cursor-pointer text-sm"
                            >
                              <span className="flex flex-wrap items-center gap-2 font-semibold">
                                {address.recipient_name}
                                <span className="rounded bg-muted px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">
                                  {address.label}
                                </span>
                                {address.is_default && (
                                  <span className="text-[11px] font-medium text-primary">
                                    {t('checkout.default')}
                                  </span>
                                )}
                              </span>
                              <span className="block text-muted-foreground">
                                {[
                                  [address.line1, address.line2].filter(Boolean).join(', '),
                                  address.landmark,
                                  address.city,
                                  address.state,
                                  address.pincode,
                                ]
                                  .filter(Boolean)
                                  .join(' · ')}
                              </span>
                              <span className="block text-muted-foreground">{address.phone}</span>
                            </label>
                          </div>
                          <div className="mt-2 flex gap-3 pl-7 text-xs font-semibold">
                            <button
                              type="button"
                              className="text-primary hover:underline"
                              onClick={() => {
                                setEditing(address);
                                setFormOpen(true);
                              }}
                            >
                              {t('checkout.edit')}
                            </button>
                            <button
                              type="button"
                              className="text-muted-foreground hover:text-destructive"
                              disabled={deleteAddress.isPending}
                              onClick={() => {
                                if (selected?.id === address.id) chooseAddress(null);
                                deleteAddress.mutate(address.id);
                              }}
                            >
                              {t('checkout.remove')}
                            </button>
                          </div>
                        </div>
                      </li>
                    );
                  })}
                </ul>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    setEditing(null);
                    setFormOpen(true);
                  }}
                >
                  <Plus aria-hidden="true" />
                  {t('checkout.addAddress')}
                </Button>
              </>
            )}
          </section>

          {/* 2. Who we call */}
          <section
            aria-labelledby="contact-heading"
            className="rounded-xl border border-border bg-card p-4"
          >
            <h2 id="contact-heading" className="mb-2 flex items-center gap-2 text-sm font-bold">
              <Phone className="size-4 text-primary" aria-hidden="true" />
              {t('checkout.contact')}
            </h2>
            {profile?.phone ? (
              <p className="flex items-center gap-2 text-sm">
                <CheckCircle2 className="size-4 text-success" aria-hidden="true" />
                {t('checkout.phoneCallNotice').replace('{phone}', profile.phone)}
              </p>
            ) : (
              <div className="space-y-2">
                <p className="text-sm text-muted-foreground">{t('checkout.phoneNeeded')}</p>
                <div className="flex flex-wrap gap-2">
                  <Input
                    aria-label={t('checkout.mobileNumber')}
                    type="tel"
                    inputMode="numeric"
                    placeholder="98765 43210"
                    value={phoneDraft}
                    onChange={(event) => setPhoneDraft(event.target.value)}
                    className="max-w-52"
                  />
                  <Button
                    size="sm"
                    disabled={savePhone.isPending || phoneDraft.replace(/\D/g, '').length < 10}
                    onClick={() => savePhone.mutate(phoneDraft)}
                  >
                    {savePhone.isPending ? t('checkout.saving') : t('checkout.saveNumber')}
                  </Button>
                </div>
                {savePhone.isError && (
                  <p role="alert" className="text-xs text-primary-700">
                    {apiErrorMessage(savePhone.error)}
                  </p>
                )}
              </div>
            )}
          </section>

          {/* 3. Notes + payment */}
          <section
            aria-labelledby="payment-heading"
            className="space-y-3 rounded-xl border border-border bg-card p-4"
          >
            <h2 id="payment-heading" className="text-sm font-bold">
              {t('checkout.payment')}
            </h2>
            <div className="flex items-start gap-3 rounded-lg bg-muted/60 p-3">
              <input
                id="payment-cod"
                type="radio"
                name="payment"
                checked
                readOnly
                className="mt-1 size-4 accent-primary"
              />
              <label htmlFor="payment-cod" className="text-sm">
                <span className="block font-semibold">{t('checkout.cod')}</span>
                <span className="block text-muted-foreground">{t('checkout.codHelp')}</span>
              </label>
            </div>
            <div>
              <label htmlFor="note" className="mb-1 block text-xs font-semibold">
                {t('checkout.noteForStore')}
              </label>
              <textarea
                id="note"
                rows={2}
                maxLength={250}
                value={note}
                onChange={(event) => setNote(event.target.value)}
                placeholder={t('checkout.notePlaceholder')}
                className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>
          </section>
        </div>

        {/* Summary */}
        <aside className="space-y-3 lg:sticky lg:top-24 lg:self-start">
          <div className="rounded-xl border border-border bg-card p-4">
            <h2 className="mb-3 text-sm font-bold">{t('checkout.summary')}</h2>
            {quote.data ? (
              <OrderTotals
                subtotalPaise={quote.data.subtotal_paise}
                deliveryFeePaise={quote.data.delivery_fee_paise}
                discountPaise={quote.data.discount_paise}
                discountReason={quote.data.discount_reason}
                walletPaise={quote.data.wallet_applied_paise}
                totalPaise={quote.data.total_paise}
                itemCount={quote.data.item_count}
              />
            ) : quote.isPending ? (
              <div className="space-y-2" role="status">
                <Skeleton className="h-4 w-2/3" />
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-6 w-3/4" />
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">{t('checkout.chooseAddress')}</p>
            )}

            {quote.data?.blocking_issues.map((issue) => (
              <p
                key={issue.code}
                role="alert"
                className="mt-3 flex gap-1.5 text-xs font-medium text-warning"
              >
                <AlertTriangle className="mt-px size-3.5 shrink-0" aria-hidden="true" />
                {blockingIssueMessage(issue)}
              </p>
            ))}

            {balance > 0 && (
              <div className="mt-3 flex items-start gap-2 rounded-lg bg-muted/60 p-2.5 text-sm">
                <input
                  id="use-wallet"
                  type="checkbox"
                  className="mt-0.5 size-4 accent-primary"
                  checked={useWallet}
                  onChange={(event) => {
                    setUseWallet(event.target.checked);
                    newAttempt();
                  }}
                  aria-describedby="wallet-help"
                />
                <label htmlFor="use-wallet">
                  <span className="font-semibold">
                    {t('checkout.useWallet').replace('{amount}', formatPaise(balance))}
                  </span>
                  <span id="wallet-help" className="block text-xs text-muted-foreground">
                    {useWallet && quote.data
                      ? t('checkout.appliedLeft')
                          .replace('{applied}', formatPaise(quote.data.wallet_applied_paise))
                          .replace('{remaining}', formatPaise(quote.data.total_paise))
                      : t('checkout.walletRemainder')}
                  </span>
                </label>
              </div>
            )}

            {quote.data?.can_checkout && (
              <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
                <Truck className="size-3.5" aria-hidden="true" />
                {t('checkout.arrivesBy')}{' '}
                {new Date(quote.data.deliver_by).toLocaleDateString(
                  getCurrentLanguage() === 'hi' ? 'hi-IN' : 'en-IN',
                  {
                    weekday: 'short',
                    day: 'numeric',
                    month: 'short',
                    timeZone: 'Asia/Kolkata',
                  },
                )}
              </p>
            )}
          </div>

          {orderError && (
            <div
              role="alert"
              className="rounded-xl border border-border bg-warning-soft p-3 text-sm text-warning"
            >
              <p className="font-semibold">{t('checkout.unableToPlace')}</p>
              <p>{apiErrorMessage(orderError)}</p>
              {typeof orderError.details.shortfall_paise === 'number' && (
                <p className="mt-1">
                  {t('checkout.addMoreToCheckout').replace(
                    '{amount}',
                    formatPaise(orderError.details.shortfall_paise),
                  )}
                </p>
              )}
            </div>
          )}

          <Button size="lg" className="w-full" disabled={!canPlace} onClick={onPlaceOrder}>
            {placeOrder.isPending
              ? t('checkout.placingOrder')
              : quote.data
                ? `${t('checkout.placeOrder')} · ${formatPaise(quote.data.total_paise)}`
                : t('checkout.placeOrder')}
          </Button>
          <p className="text-center text-xs text-muted-foreground">
            {quote.data && quote.data.total_paise === 0
              ? t('checkout.walletCovers')
              : t('checkout.payOnDelivery').replace(
                  '{amount}',
                  quote.data ? formatPaise(quote.data.total_paise) : '—',
                )}{' '}
            {t('checkout.cancelUntil')}
          </p>
        </aside>
      </div>
    </div>
  );
}
