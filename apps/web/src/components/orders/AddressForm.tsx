import { zodResolver } from '@hookform/resolvers/zod';
import type { AddressIn, AddressOut } from '@tripat/api-client';
import type { ReactNode } from 'react';
import { useForm } from 'react-hook-form';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { addressSchema, toAddressIn, type AddressFormValues } from '@/features/orders/address';

const EMPTY: AddressFormValues = {
  recipient_name: '',
  phone: '',
  line1: '',
  line2: '',
  landmark: '',
  city: 'Gurugram',
  state: 'Haryana',
  pincode: '',
  label: 'Home',
  is_default: false,
};

function fromAddress(address: AddressOut | null | undefined): AddressFormValues {
  if (!address) return EMPTY;
  return {
    recipient_name: address.recipient_name,
    phone: address.phone,
    line1: address.line1,
    line2: address.line2 ?? '',
    landmark: address.landmark ?? '',
    city: address.city,
    state: address.state ?? '',
    pincode: address.pincode,
    label: address.label,
    is_default: address.is_default,
  };
}

/**
 * Delivery address form.
 *
 * Validation mirrors the API's own rules (10-digit Indian mobile, 6-digit
 * pincode) so the shopper gets the message next to the field instead of after a
 * round trip — but the API is still the authority, and its `fields` errors are
 * mapped back onto the inputs by the caller.
 */
export function AddressForm({
  address,
  submitting,
  serverError,
  onSubmit,
  onCancel,
}: {
  /** Present when editing an existing address. */
  address?: AddressOut | null;
  submitting: boolean;
  serverError?: string | null;
  onSubmit: (values: AddressIn) => void;
  onCancel?: () => void;
}) {
  const form = useForm<AddressFormValues>({
    resolver: zodResolver(addressSchema),
    defaultValues: fromAddress(address),
  });
  const errors = form.formState.errors;

  return (
    <form
      className="space-y-3 rounded-xl border border-border bg-card p-4"
      noValidate
      onSubmit={(event) => {
        void form.handleSubmit((values) => onSubmit(toAddressIn(values)))(event);
      }}
    >
      <h2 className="text-sm font-bold">{address ? 'Edit address' : 'New delivery address'}</h2>

      {serverError && (
        <p role="alert" className="rounded-lg bg-warning-soft p-2 text-xs font-medium text-warning">
          {serverError}
        </p>
      )}

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Full name" error={errors.recipient_name?.message} htmlFor="recipient_name">
          <Input
            id="recipient_name"
            autoComplete="name"
            aria-invalid={Boolean(errors.recipient_name)}
            {...form.register('recipient_name')}
          />
        </Field>
        <Field label="Mobile number" error={errors.phone?.message} htmlFor="phone">
          <Input
            id="phone"
            type="tel"
            inputMode="numeric"
            autoComplete="tel-national"
            placeholder="98765 43210"
            aria-invalid={Boolean(errors.phone)}
            {...form.register('phone')}
          />
        </Field>
      </div>

      <Field label="House / flat, street" error={errors.line1?.message} htmlFor="line1">
        <Input
          id="line1"
          autoComplete="address-line1"
          aria-invalid={Boolean(errors.line1)}
          {...form.register('line1')}
        />
      </Field>

      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Area / locality (optional)" error={errors.line2?.message} htmlFor="line2">
          <Input id="line2" autoComplete="address-line2" {...form.register('line2')} />
        </Field>
        <Field label="Landmark (optional)" error={errors.landmark?.message} htmlFor="landmark">
          <Input id="landmark" placeholder="Near the school gate" {...form.register('landmark')} />
        </Field>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
        <Field label="Pincode" error={errors.pincode?.message} htmlFor="pincode">
          <Input
            id="pincode"
            inputMode="numeric"
            maxLength={6}
            autoComplete="postal-code"
            aria-invalid={Boolean(errors.pincode)}
            {...form.register('pincode')}
          />
        </Field>
        <Field label="Town / city" error={errors.city?.message} htmlFor="city">
          <Input id="city" autoComplete="address-level2" {...form.register('city')} />
        </Field>
        <Field label="State" error={errors.state?.message} htmlFor="state">
          <Input id="state" autoComplete="address-level1" {...form.register('state')} />
        </Field>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 pt-1">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            className="size-4 accent-primary"
            {...form.register('is_default')}
          />
          Use as my default address
        </label>
        <div className="flex gap-2">
          {onCancel && (
            <Button type="button" variant="outline" size="sm" onClick={onCancel}>
              Cancel
            </Button>
          )}
          <Button type="submit" size="sm" disabled={submitting}>
            {submitting ? 'Saving…' : address ? 'Save changes' : 'Save address'}
          </Button>
        </div>
      </div>
    </form>
  );
}

function Field({
  label,
  htmlFor,
  error,
  children,
}: {
  label: string;
  htmlFor: string;
  error?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <label htmlFor={htmlFor} className="mb-1 block text-xs font-semibold">
        {label}
      </label>
      {children}
      {error && <p className="mt-1 text-xs text-primary-700">{error}</p>}
    </div>
  );
}
