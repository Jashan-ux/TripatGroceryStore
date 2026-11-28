import type { SettingsOut, SettingsPatchIn } from '@tripat/api-client';
import { useState } from 'react';

import { useAdminSettings, useUpdateSettings } from '@/admin/adminCatalogue';
import {
  useDeliveryCandidates,
  useDeliveryProfiles,
  usePromoteDeliveryProfile,
} from '@/admin/adminDelivery';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { usePageTitle } from '@/hooks/usePageTitle';

/** Money fields are edited in rupees; the API speaks paise. */
function toPaise(value: string): number {
  const rupees = Number(value.replace(/[^\d.]/g, ''));
  return Number.isFinite(rupees) ? Math.round(rupees * 100) : 0;
}

function toRupees(paise: number): string {
  return (paise / 100).toFixed(2);
}

type MoneyField =
  | 'minimum_order_paise'
  | 'referral_referrer_reward_paise'
  | 'scratch_threshold_paise'
  | 'scratch_min_paise'
  | 'scratch_max_paise'
  | 'tier_gold_paise'
  | 'tier_platinum_paise'
  | 'tier_diamond_paise';

const MONEY_FIELDS: { field: MoneyField; label: string; hint: string }[] = [
  {
    field: 'minimum_order_paise',
    label: 'Minimum order',
    hint: 'A cart below this cannot be checked out.',
  },
  {
    field: 'referral_referrer_reward_paise',
    label: 'Referral reward for the person who invited',
    hint: 'Paid into the wallet after their friend’s first delivered order.',
  },
  {
    field: 'scratch_threshold_paise',
    label: 'Scratch card is unlocked at',
    hint: 'Delivered-order value that earns a scratch card.',
  },
  { field: 'scratch_min_paise', label: 'Smallest prize', hint: 'Never less than this.' },
  { field: 'scratch_max_paise', label: 'Largest prize', hint: 'Never more than this.' },
  { field: 'tier_gold_paise', label: 'Gold tier at', hint: 'Lifetime spend.' },
  { field: 'tier_platinum_paise', label: 'Platinum tier at', hint: 'Lifetime spend.' },
  { field: 'tier_diamond_paise', label: 'Diamond tier at', hint: 'Lifetime spend.' },
];

const NUMBER_FIELDS: {
  field: keyof SettingsOut &
    (
      | 'default_delivery_days'
      | 'low_stock_threshold'
      | 'return_window_days'
      | 'scratch_expiry_days'
      | 'referral_friend_discount_pct'
    );
  label: string;
  hint: string;
}[] = [
  {
    field: 'default_delivery_days',
    label: 'Delivery days',
    hint: 'How long a new order usually takes.',
  },
  {
    field: 'low_stock_threshold',
    label: 'Low-stock alert at',
    hint: 'Products at or below this show up in the low-stock filter.',
  },
  {
    field: 'return_window_days',
    label: 'Return window (days)',
    hint: 'How long after delivery a return is allowed.',
  },
  {
    field: 'scratch_expiry_days',
    label: 'Scratch card expires after (days)',
    hint: 'Unused cards lapse after this.',
  },
  {
    field: 'referral_friend_discount_pct',
    label: 'Friend’s discount (%)',
    hint: 'Applied to their first order.',
  },
];

/**
 * Every number the shop runs on, in one place.
 *
 * The page saves only what the owner touched, and the server answers with the
 * whole row — so a rejected change (say gold above platinum) is visible without
 * a reload. The note under the button is the promise this feature exists for:
 * a saved number applies to the *next* checkout, with no deploy.
 */
export function AdminSettingsPage() {
  usePageTitle(undefined, 'Settings · Admin');
  const settings = useAdminSettings();
  if (settings.isPending) {
    return (
      <div className="container max-w-3xl py-5" role="status">
        <Skeleton className="h-72 w-full rounded-xl" />
      </div>
    );
  }
  if (settings.isError || !settings.data) {
    return (
      <div className="container max-w-3xl space-y-3 py-5" role="alert">
        <p className="text-sm text-warning">
          {settings.error?.message ?? 'Settings could not be loaded.'}
        </p>
        <Button variant="outline" onClick={() => void settings.refetch()}>
          Try again
        </Button>
      </div>
    );
  }
  return <SettingsForm settings={settings.data} />;
}

function SettingsForm({ settings }: { settings: SettingsOut }) {
  const update = useUpdateSettings();
  const profiles = useDeliveryProfiles();
  const candidates = useDeliveryCandidates('');
  const promote = usePromoteDeliveryProfile();
  const [candidateId, setCandidateId] = useState('');
  const [form, setForm] = useState(settings);
  // Rupee fields are edited as text and converted once, on save. Re-formatting a
  // live controlled input ("5" → "5.00" → "5.005") fights the person typing.
  const [rupees, setRupees] = useState<Record<MoneyField, string>>(() => ({
    minimum_order_paise: toRupees(settings.minimum_order_paise),
    referral_referrer_reward_paise: toRupees(settings.referral_referrer_reward_paise),
    scratch_threshold_paise: toRupees(settings.scratch_threshold_paise),
    scratch_min_paise: toRupees(settings.scratch_min_paise),
    scratch_max_paise: toRupees(settings.scratch_max_paise),
    tier_gold_paise: toRupees(settings.tier_gold_paise),
    tier_platinum_paise: toRupees(settings.tier_platinum_paise),
    tier_diamond_paise: toRupees(settings.tier_diamond_paise),
  }));
  // Pincodes are typed as free text and parsed on save, for the same reason.
  const [pincodes, setPincodes] = useState((settings.serviceable_pincodes ?? []).join(', '));
  const [notice, setNotice] = useState<string | null>(null);

  const save = () => {
    setNotice(null);
    const patch: SettingsPatchIn = {
      store_name: form.store_name,
      store_phone: form.store_phone,
      store_address: form.store_address,
      store_maps_url: form.store_maps_url,
      feedback_email: form.feedback_email,
      notification_email: form.notification_email,
      serviceable_pincodes: pincodes
        .split(/[\s,]+/)
        .map((entry) => entry.trim())
        .filter(Boolean),
      minimum_order_paise: toPaise(rupees.minimum_order_paise),
      referral_referrer_reward_paise: toPaise(rupees.referral_referrer_reward_paise),
      referral_friend_discount_pct: form.referral_friend_discount_pct,
      scratch_threshold_paise: toPaise(rupees.scratch_threshold_paise),
      scratch_min_paise: toPaise(rupees.scratch_min_paise),
      scratch_max_paise: toPaise(rupees.scratch_max_paise),
      scratch_expiry_days: form.scratch_expiry_days,
      return_window_days: form.return_window_days,
      low_stock_threshold: form.low_stock_threshold,
      default_delivery_days: form.default_delivery_days,
      default_delivery_profile_id: form.default_delivery_profile_id ?? null,
      is_open: form.is_open,
      tier_gold_paise: toPaise(rupees.tier_gold_paise),
      tier_platinum_paise: toPaise(rupees.tier_platinum_paise),
      tier_diamond_paise: toPaise(rupees.tier_diamond_paise),
    };
    update.mutate(patch, {
      onSuccess: (saved) => {
        setForm(saved);
        setPincodes((saved.serviceable_pincodes ?? []).join(', '));
        setRupees({
          minimum_order_paise: toRupees(saved.minimum_order_paise),
          referral_referrer_reward_paise: toRupees(saved.referral_referrer_reward_paise),
          scratch_threshold_paise: toRupees(saved.scratch_threshold_paise),
          scratch_min_paise: toRupees(saved.scratch_min_paise),
          scratch_max_paise: toRupees(saved.scratch_max_paise),
          tier_gold_paise: toRupees(saved.tier_gold_paise),
          tier_platinum_paise: toRupees(saved.tier_platinum_paise),
          tier_diamond_paise: toRupees(saved.tier_diamond_paise),
        });
        setNotice('Saved. The next checkout already uses these numbers.');
      },
    });
  };

  return (
    <div className="container max-w-3xl space-y-4 py-5 pb-nav-safe md:pb-8">
      <h1 className="text-xl font-extrabold tracking-tight">Settings</h1>

      <section className="space-y-2 rounded-xl border border-border bg-card p-3">
        <h2 className="text-sm font-bold">The shop</h2>
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-border p-3">
          <div>
            <p className="text-sm font-semibold">Store availability</p>
            <p className="text-xs text-muted-foreground">
              {form.is_open
                ? 'Customers can place orders.'
                : 'Ordering is paused. Existing orders are unaffected.'}
            </p>
          </div>
          <Button
            type="button"
            variant={form.is_open ? 'primary' : 'outline'}
            aria-pressed={form.is_open}
            onClick={() => setForm({ ...form, is_open: !form.is_open })}
          >
            {form.is_open ? 'Open' : 'Closed'}
          </Button>
        </div>
        <label className="block text-xs font-semibold" htmlFor="name">
          Name
          <Input
            id="name"
            className="mt-1"
            value={form.store_name}
            onChange={(event) => setForm({ ...form, store_name: event.target.value })}
          />
        </label>
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="text-xs font-semibold" htmlFor="phone">
            Phone
            <Input
              id="phone"
              className="mt-1"
              inputMode="tel"
              value={form.store_phone}
              onChange={(event) => setForm({ ...form, store_phone: event.target.value })}
            />
          </label>
          <label className="text-xs font-semibold" htmlFor="google-maps-link">
            Google Maps link
            <Input
              id="google-maps-link"
              className="mt-1"
              value={form.store_maps_url}
              onChange={(event) => setForm({ ...form, store_maps_url: event.target.value })}
              placeholder="https://maps.app.goo.gl/…"
            />
          </label>
        </div>
        <label className="block text-xs font-semibold" htmlFor="address">
          Address
          <Textarea
            id="address"
            className="mt-1"
            rows={2}
            value={form.store_address}
            onChange={(event) => setForm({ ...form, store_address: event.target.value })}
          />
        </label>
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="text-xs font-semibold" htmlFor="feedback-goes-to">
            Feedback goes to
            <Input
              id="feedback-goes-to"
              className="mt-1"
              type="email"
              value={form.feedback_email}
              onChange={(event) => setForm({ ...form, feedback_email: event.target.value })}
            />
          </label>
          <label className="text-xs font-semibold" htmlFor="order-alerts-go-to">
            Order alerts go to
            <Input
              id="order-alerts-go-to"
              className="mt-1"
              type="email"
              value={form.notification_email}
              onChange={(event) => setForm({ ...form, notification_email: event.target.value })}
            />
          </label>
        </div>
      </section>

      <section className="space-y-3 rounded-xl border border-border bg-card p-3">
        <div>
          <h2 className="text-sm font-bold">Delivery worker</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Set up the worker’s normal customer account first. Once enabled here, they get a
            delivery-only view; newly shipped orders are assigned to the default worker.
          </p>
        </div>
        <label className="block text-xs font-semibold" htmlFor="default-delivery-profile">
          Default delivery person
          <Select
            id="default-delivery-profile"
            className="mt-1"
            value={form.default_delivery_profile_id ?? ''}
            disabled={profiles.isPending || profiles.isError}
            onChange={(event) =>
              setForm({
                ...form,
                default_delivery_profile_id: event.target.value || null,
              })
            }
          >
            <option value="">No default driver</option>
            {(profiles.data ?? []).map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.name}
                {profile.phone ? ` · ${profile.phone}` : ''}
              </option>
            ))}
          </Select>
        </label>
        {profiles.isPending && (
          <p role="status" className="text-xs">
            Loading delivery profiles…
          </p>
        )}
        {profiles.isError && (
          <div
            role="alert"
            className="flex items-center justify-between gap-2 text-xs text-warning"
          >
            <span>{profiles.error.message}</span>
            <Button size="sm" variant="outline" onClick={() => void profiles.refetch()}>
              Try again
            </Button>
          </div>
        )}
        <div className="grid gap-2 sm:grid-cols-[1fr_auto] sm:items-end">
          <label className="block text-xs font-semibold" htmlFor="enable-delivery-profile">
            Enable an existing account for delivery
            <Select
              id="enable-delivery-profile"
              className="mt-1"
              value={candidateId}
              disabled={candidates.isPending || candidates.isError || !candidates.data?.length}
              onChange={(event) => setCandidateId(event.target.value)}
            >
              <option value="">Choose a customer account</option>
              {(candidates.data ?? []).map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name} · {profile.email}
                </option>
              ))}
            </Select>
          </label>
          <Button
            type="button"
            variant="outline"
            disabled={!candidateId || promote.isPending}
            onClick={() =>
              promote.mutate(candidateId, {
                onSuccess: (profile) => {
                  setForm({ ...form, default_delivery_profile_id: profile.id });
                  setCandidateId('');
                  setNotice(
                    'Delivery access enabled. Save settings to make this worker the default.',
                  );
                },
              })
            }
          >
            {promote.isPending ? 'Enabling…' : 'Enable driver'}
          </Button>
        </div>
        {candidates.isPending && (
          <p role="status" className="text-xs">
            Loading customer accounts…
          </p>
        )}
        {candidates.isError && (
          <div
            role="alert"
            className="flex items-center justify-between gap-2 text-xs text-warning"
          >
            <span>{candidates.error.message}</span>
            <Button size="sm" variant="outline" onClick={() => void candidates.refetch()}>
              Try again
            </Button>
          </div>
        )}
        {candidates.isSuccess && candidates.data.length === 0 && (
          <div className="flex items-center justify-between gap-2 text-xs text-muted-foreground">
            <span>No customer accounts are available. The worker must sign up first.</span>
            <Button size="sm" variant="outline" onClick={() => void candidates.refetch()}>
              Refresh
            </Button>
          </div>
        )}
        {promote.isError && (
          <p role="alert" className="text-xs text-warning">
            {promote.error.message}
          </p>
        )}
      </section>

      <section className="space-y-2 rounded-xl border border-border bg-card p-3">
        <h2 className="text-sm font-bold">Money</h2>
        <div className="grid gap-2 sm:grid-cols-2">
          {MONEY_FIELDS.map(({ field, label, hint }) => (
            <label key={field} className="text-xs font-semibold">
              {label} (₹)
              <Input
                className="mt-1"
                inputMode="decimal"
                value={rupees[field]}
                onChange={(event) => setRupees({ ...rupees, [field]: event.target.value })}
              />
              <span className="mt-0.5 block text-[11px] font-normal text-muted-foreground">
                {hint}
              </span>
            </label>
          ))}
        </div>
      </section>

      <section className="space-y-2 rounded-xl border border-border bg-card p-3">
        <h2 className="text-sm font-bold">Operations</h2>
        <div className="grid gap-2 sm:grid-cols-2">
          {NUMBER_FIELDS.map(({ field, label, hint }) => (
            <label key={field} className="text-xs font-semibold">
              {label}
              <Input
                className="mt-1"
                inputMode="numeric"
                value={String(form[field])}
                onChange={(event) =>
                  setForm({ ...form, [field]: Number(event.target.value.replace(/\D/g, '')) })
                }
              />
              <span className="mt-0.5 block text-[11px] font-normal text-muted-foreground">
                {hint}
              </span>
            </label>
          ))}
        </div>
        <label
          className="block text-xs font-semibold"
          htmlFor="serviceable-pincodes-comma-separated"
        >
          Serviceable pincodes (comma separated)
          <Textarea
            id="serviceable-pincodes-comma-separated"
            className="mt-1 font-mono text-xs"
            rows={2}
            value={pincodes}
            onChange={(event) => setPincodes(event.target.value)}
          />
        </label>
      </section>

      {notice && (
        <p
          role="status"
          className="rounded-lg bg-success-soft p-2.5 text-sm font-medium text-success"
        >
          {notice}
        </p>
      )}
      {update.isError && (
        <p
          role="alert"
          className="rounded-lg bg-warning-soft p-2.5 text-sm font-medium text-warning"
        >
          {update.error.message}
        </p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={save} disabled={update.isPending} size="lg">
          {update.isPending ? 'Saving…' : 'Save settings'}
        </Button>
        <p className="text-xs text-muted-foreground">
          Applies on the next checkout — no redeploy. Every change is recorded in Activity.
        </p>
      </div>
    </div>
  );
}
