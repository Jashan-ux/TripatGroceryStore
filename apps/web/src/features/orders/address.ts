import { z } from 'zod';

import type { AddressIn } from '@tripat/api-client';

/**
 * Address validation, shared by the form and the API tests.
 *
 * The rules mirror the API's own (10-digit Indian mobile, 6-digit pincode) so
 * the shopper gets the message next to the field instead of after a round trip —
 * the API remains the authority.
 */
export const addressSchema = z.object({
  recipient_name: z.string().trim().min(2, 'Who should we ask for?').max(80),
  phone: z
    .string()
    .trim()
    .regex(/^(\+?91[\s-]?)?[6-9]\d{9}$/, 'Enter a 10-digit Indian mobile number'),
  line1: z.string().trim().min(5, 'Add the house / flat number and street').max(200),
  line2: z.string().trim().max(200),
  landmark: z.string().trim().max(120),
  city: z.string().trim().min(2, 'Add your town or city').max(80),
  state: z.string().trim().max(80),
  pincode: z
    .string()
    .trim()
    .regex(/^\d{6}$/, 'Enter the 6-digit pincode'),
  label: z.string().trim().max(40),
  is_default: z.boolean(),
});

export type AddressFormValues = z.infer<typeof addressSchema>;

export function toAddressIn(values: AddressFormValues): AddressIn {
  return {
    recipient_name: values.recipient_name.trim(),
    phone: values.phone.trim(),
    line1: values.line1.trim(),
    line2: values.line2.trim(),
    landmark: values.landmark.trim(),
    city: values.city.trim(),
    state: values.state.trim(),
    pincode: values.pincode.trim(),
    label: values.label.trim() || 'Home',
    is_default: values.is_default,
  };
}
