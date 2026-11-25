import { zodResolver } from '@hookform/resolvers/zod';
import { MailCheck } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link } from 'react-router-dom';
import { z } from 'zod';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/features/auth/useAuth';
import { authErrorMessage } from '@/features/auth/errors';
import { usePageTitle } from '@/hooks/usePageTitle';

const schema = z.object({
  email: z.string().trim().min(1, 'Enter your email').email('Enter a valid email address'),
});
type FormValues = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  usePageTitle('auth.signInTitle');
  const { sendPasswordReset } = useAuth();
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const form = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { email: '' } });

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      await sendPasswordReset(values.email.trim().toLowerCase());
      setSent(true);
    } catch (caught) {
      setError(authErrorMessage(caught, 'We could not send the reset email. Please try again.'));
    }
  });

  if (sent) {
    return (
      <div className="container max-w-md py-10">
        <MailCheck className="mb-3 size-10 text-primary" aria-hidden="true" />
        <h1 className="text-2xl font-extrabold">Check your email</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          If that address has an account, a reset link is on its way. The link expires in one hour.
        </p>
        <Button asChild className="mt-6 w-full" variant="outline">
          <Link to="/sign-in">Back to sign in</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="container max-w-md py-8">
      <h1 className="text-2xl font-extrabold tracking-tight">Reset your password</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        We will email you a link to choose a new password.
      </p>
      <form
        onSubmit={(event) => {
          void onSubmit(event);
        }}
        className="mt-6 space-y-4"
        noValidate
      >
        <div>
          <label htmlFor="email" className="mb-1 block text-sm font-semibold">
            Email
          </label>
          <Input id="email" type="email" autoComplete="email" {...form.register('email')} />
          {form.formState.errors.email && (
            <p className="mt-1 text-xs text-primary-700">{form.formState.errors.email.message}</p>
          )}
        </div>
        {error && (
          <p className="rounded-lg bg-primary-50 p-3 text-sm text-primary-900" role="alert">
            {error}
          </p>
        )}
        <Button type="submit" size="lg" className="w-full" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? 'Sending…' : 'Send reset link'}
        </Button>
      </form>
    </div>
  );
}
