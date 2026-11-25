import { zodResolver } from '@hookform/resolvers/zod';
import { MailCheck, UserPlus } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, useSearchParams } from 'react-router-dom';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/features/auth/useAuth';
import { authErrorMessage } from '@/features/auth/errors';
import { usePageTitle } from '@/hooks/usePageTitle';

const schema = z
  .object({
    name: z.string().trim().min(2, 'Tell us your name').max(120, 'That name is too long'),
    email: z.string().trim().min(1, 'Enter your email').email('Enter a valid email address'),
    password: z.string().min(8, 'Use at least 8 characters'),
    confirmPassword: z.string(),
  })
  .refine((values) => values.password === values.confirmPassword, {
    path: ['confirmPassword'],
    message: 'The passwords do not match',
  });

type FormValues = z.infer<typeof schema>;

export default function SignUpPage() {
  usePageTitle('auth.signUpTitle');
  const { signUpWithPassword, authAvailable } = useAuth();
  const [params] = useSearchParams();
  const [serverError, setServerError] = useState<string | null>(null);
  const [done, setDone] = useState<null | { needsEmailConfirmation: boolean }>(null);
  const next = params.get('next');

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { name: '', email: '', password: '', confirmPassword: '' },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    setServerError(null);
    try {
      const result = await signUpWithPassword(
        values.email.trim().toLowerCase(),
        values.password,
        values.name.trim(),
      );
      setDone(result);
    } catch (error) {
      setServerError(authErrorMessage(error, 'We could not create your account. Please try again.'));
    }
  });

  if (done) {
    return (
      <div className="container max-w-md py-10">
        <MailCheck className="mb-3 size-10 text-primary" aria-hidden="true" />
        <h1 className="text-2xl font-extrabold tracking-tight">
          {done.needsEmailConfirmation ? 'Check your email' : 'You are all set'}
        </h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {done.needsEmailConfirmation
            ? 'We sent a confirmation link. Tap it and you will land back here, signed in.'
            : 'Your account is ready.'}
        </p>
        <Button asChild className="mt-6 w-full" size="lg">
          <Link to={next ?? '/profile'}>{done.needsEmailConfirmation ? 'Go to profile' : 'Continue'}</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="container max-w-md py-8">
      <h1 className="text-2xl font-extrabold tracking-tight">Create your account</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        One account for orders, wallet credit and referral rewards.
      </p>

      {!authAvailable && (
        <p className="mt-4 rounded-xl bg-warning-soft p-3 text-sm text-warning" role="alert">
          Sign-up is not configured for this build. Please call the store to place an order.
        </p>
      )}

      <form
        onSubmit={(event) => {
          void onSubmit(event);
        }}
        className="mt-6 space-y-4"
        noValidate
      >
        {(
          [
            { name: 'name', label: 'Your name', type: 'text', autoComplete: 'name' },
            { name: 'email', label: 'Email', type: 'email', autoComplete: 'email' },
            { name: 'password', label: 'Password', type: 'password', autoComplete: 'new-password' },
            {
              name: 'confirmPassword',
              label: 'Confirm password',
              type: 'password',
              autoComplete: 'new-password',
            },
          ] as const
        ).map((field) => {
          const error = form.formState.errors[field.name];
          return (
            <div key={field.name}>
              <label htmlFor={field.name} className="mb-1 block text-sm font-semibold">
                {field.label}
              </label>
              <Input
                id={field.name}
                type={field.type}
                autoComplete={field.autoComplete}
                aria-invalid={Boolean(error)}
                aria-describedby={error ? `${field.name}-error` : undefined}
                {...form.register(field.name)}
              />
              {error && (
                <p id={`${field.name}-error`} className="mt-1 text-xs text-primary-700">
                  {error.message}
                </p>
              )}
            </div>
          );
        })}

        {serverError && (
          <p className="rounded-lg bg-primary-50 p-3 text-sm text-primary-900" role="alert">
            {serverError}
          </p>
        )}

        <Button type="submit" size="lg" className="w-full" disabled={form.formState.isSubmitting}>
          <UserPlus aria-hidden="true" />
          {form.formState.isSubmitting ? 'Creating account…' : 'Create account'}
        </Button>
      </form>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        Already have an account?{' '}
        <Link to="/sign-in" className="font-semibold text-primary-700">
          Sign in
        </Link>
      </p>
    </div>
  );
}
