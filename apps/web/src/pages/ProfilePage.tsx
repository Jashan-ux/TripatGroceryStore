import type { ProfileOut } from '@tripat/api-client';
import { zodResolver } from '@hookform/resolvers/zod';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { BadgeCheck, Copy, LogOut, Phone, Settings, Trophy, UserRound } from 'lucide-react';
import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, useLocation } from 'react-router-dom';
import { toast } from 'sonner';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { useAuth } from '@/features/auth/useAuth';
import { usePageTitle } from '@/hooks/usePageTitle';
import { api, type ApiError } from '@/lib/api';
import { formatPaise } from '@/lib/utils';

const nameSchema = z.object({
  name: z.string().trim().min(2, 'Enter your name').max(120, 'That name is too long'),
});
type NameValues = z.infer<typeof nameSchema>;

const phoneSchema = z.object({
  phone: z
    .string()
    .trim()
    .min(10, 'Enter a 10-digit mobile number')
    .regex(
      /^(\+?91[\s-]?)?[6-9]\d{9}$|^0?[6-9]\d{9}$/,
      'That does not look like an Indian mobile number',
    ),
});
type PhoneValues = z.infer<typeof phoneSchema>;

const TIER_LABELS: Record<string, string> = {
  none: 'Member',
  gold: 'Gold',
  platinum: 'Platinum',
  diamond: 'Diamond',
};

export default function ProfilePage() {
  usePageTitle('nav.profile');
  const { profile, isAdmin, signOut, refreshProfile, status } = useAuth();
  const queryClient = useQueryClient();
  const location = useLocation();
  const [copyState, setCopyState] = useState<'idle' | 'done'>('idle');

  const nameForm = useForm<NameValues>({
    resolver: zodResolver(nameSchema),
    defaultValues: { name: profile?.name ?? '' },
  });
  const phoneForm = useForm<PhoneValues>({
    resolver: zodResolver(phoneSchema),
    defaultValues: { phone: profile?.phone ?? '' },
  });

  // Keep the forms in step with the server copy (first paint arrives after auth).
  useEffect(() => {
    if (profile) {
      nameForm.reset({ name: profile.name });
      phoneForm.reset({ phone: profile.phone ?? '' });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profile?.id, profile?.name, profile?.phone]);

  const updateName = useMutation<ProfileOut, ApiError, NameValues>({
    mutationFn: (values) => api.patch<ProfileOut>('/api/v1/me', { name: values.name }),
    onSuccess: async () => {
      toast.success('Name updated');
      await refreshProfile();
    },
    onError: (error) => toast.error(error.message),
  });

  const updatePhone = useMutation<ProfileOut, ApiError, PhoneValues>({
    mutationFn: (values) => api.post<ProfileOut>('/api/v1/me/phone', { phone: values.phone }),
    onSuccess: async () => {
      toast.success('Mobile number saved');
      await refreshProfile();
      await queryClient.invalidateQueries({ queryKey: ['me'] });
      phoneForm.reset({ phone: '' });
      phoneForm.setValue('phone', '');
    },
    onError: (error) => {
      if (error.code === 'phone_already_used') {
        phoneForm.setError('phone', { message: error.message });
        return;
      }
      toast.error(error.message);
    },
  });

  if (status === 'loading' || !profile) {
    return (
      <div className="container space-y-3 py-6">
        <Skeleton className="h-24 w-full rounded-2xl" />
        <Skeleton className="h-40 w-full rounded-2xl" />
      </div>
    );
  }

  const copyReferral = async () => {
    try {
      await navigator.clipboard.writeText(profile.referral_code);
      setCopyState('done');
      toast.success('Referral code copied');
      window.setTimeout(() => setCopyState('idle'), 2000);
    } catch {
      toast.error('Copy failed — long-press the code to copy it.');
    }
  };

  return (
    <div className="container max-w-2xl space-y-4 py-6">
      <header className="flex items-center gap-3 rounded-2xl border border-border bg-card p-4 shadow-elev1">
        <div className="flex size-12 items-center justify-center rounded-full bg-primary-50 text-primary-800">
          <UserRound className="size-6" aria-hidden="true" />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-lg font-extrabold tracking-tight">
            {profile.name || 'Your account'}
          </h1>
          <p className="truncate text-sm text-muted-foreground">{profile.email}</p>
        </div>
        <BadgeCheck className="size-5 text-success" aria-label="Account verified" />
      </header>

      <section className="grid gap-3 sm:grid-cols-3" aria-label="Account summary">
        <div className="rounded-xl border border-border bg-card p-3">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Tier</p>
          <p className="mt-1 text-base font-bold">
            {TIER_LABELS[profile.loyalty_tier] ?? 'Member'}
          </p>
        </div>
        <div className="rounded-xl border border-border bg-card p-3">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Lifetime spend</p>
          <p className="mt-1 text-base font-bold">{formatPaise(profile.lifetime_spend_paise)}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-3">
          <p className="text-xs uppercase tracking-wide text-muted-foreground">Mobile</p>
          <p className="mt-1 text-base font-bold">{profile.phone ?? 'Not added'}</p>
        </div>
      </section>

      <section id="phone" className="rounded-2xl border border-border bg-card p-4">
        <h2 className="flex items-center gap-2 text-base font-bold">
          <Phone className="size-4 text-primary" aria-hidden="true" />
          {profile.phone ? 'Change mobile number' : 'Add mobile number'}
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          The delivery partner calls this number. We never share it.
        </p>
        <form
          className="mt-3 flex flex-col gap-2 sm:flex-row"
          onSubmit={(event) => {
            void phoneForm.handleSubmit((values) => updatePhone.mutate(values))(event);
          }}
          noValidate
        >
          <div className="flex-1">
            <label htmlFor="phone" className="sr-only">
              Mobile number
            </label>
            <Input
              id="phone"
              type="tel"
              inputMode="tel"
              autoComplete="tel-national"
              placeholder="+91 87089-73386"
              aria-invalid={Boolean(phoneForm.formState.errors.phone)}
              {...phoneForm.register('phone')}
            />
            {phoneForm.formState.errors.phone && (
              <p className="mt-1 text-xs text-primary-700">
                {phoneForm.formState.errors.phone.message}
              </p>
            )}
          </div>
          <Button type="submit" disabled={updatePhone.isPending}>
            {updatePhone.isPending ? 'Saving…' : 'Save'}
          </Button>
        </form>
      </section>

      <section className="rounded-2xl border border-border bg-card p-4">
        <h2 className="text-base font-bold">Your name</h2>
        <form
          className="mt-3 flex flex-col gap-2 sm:flex-row"
          onSubmit={(event) => {
            void nameForm.handleSubmit((values) => updateName.mutate(values))(event);
          }}
          noValidate
        >
          <div className="flex-1">
            <label htmlFor="name" className="sr-only">
              Full name
            </label>
            <Input
              id="name"
              autoComplete="name"
              aria-invalid={Boolean(nameForm.formState.errors.name)}
              {...nameForm.register('name')}
            />
            {nameForm.formState.errors.name && (
              <p className="mt-1 text-xs text-primary-700">
                {nameForm.formState.errors.name.message}
              </p>
            )}
          </div>
          <Button type="submit" variant="outline" disabled={updateName.isPending}>
            {updateName.isPending ? 'Saving…' : 'Update'}
          </Button>
        </form>
      </section>

      <section className="rounded-2xl border border-border bg-card p-4">
        <h2 className="text-base font-bold">Refer a friend</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Share your code. Your friend gets 10% off their first order, and you earn credit once that
          order is delivered.
        </p>
        <div className="mt-3 flex items-center gap-2">
          <code className="min-h-touch flex-1 rounded-lg border border-dashed border-border bg-muted/60 px-3 py-2 font-mono text-base font-bold tracking-widest">
            {profile.referral_code}
          </code>
          <Button
            variant="outline"
            onClick={() => {
              void copyReferral();
            }}
            aria-live="polite"
          >
            <Copy aria-hidden="true" />
            {copyState === 'done' ? 'Copied' : 'Copy'}
          </Button>
        </div>
      </section>

      <Button asChild variant="outline" className="w-full">
        <Link to="/rewards">
          <Trophy aria-hidden="true" />
          Wallet, cards and returns
        </Link>
      </Button>

      <div className="flex flex-col gap-2 pt-1 sm:flex-row">
        {isAdmin && (
          <Button asChild variant="outline" className="sm:flex-1">
            <Link to="/admin">
              <Settings aria-hidden="true" />
              Owner dashboard
            </Link>
          </Button>
        )}
        <Button
          variant="ghost"
          className="sm:flex-1"
          onClick={() => {
            void signOut();
            toast.success('Signed out');
          }}
        >
          <LogOut aria-hidden="true" />
          Sign out
        </Button>
      </div>

      {location.hash === '#phone' && (
        <p className="text-center text-xs text-muted-foreground">
          Adding a number takes a few seconds and is used only for delivery.
        </p>
      )}
    </div>
  );
}
