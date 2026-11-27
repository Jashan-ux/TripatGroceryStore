import { zodResolver } from '@hookform/resolvers/zod';
import { LogIn } from 'lucide-react';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { z } from 'zod';

import { CallStoreButton } from '@/components/common/CallStoreButton';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { useAuth } from '@/features/auth/useAuth';
import { authErrorMessage } from '@/features/auth/errors';
import { usePageTitle } from '@/hooks/usePageTitle';
import { safeInternalPath } from '@/lib/navigation';

const schema = z.object({
  email: z.string().trim().min(1, 'Enter your email').email('Enter a valid email address'),
  password: z.string().min(1, 'Enter your password'),
});

type FormValues = z.infer<typeof schema>;

export default function SignInPage() {
  usePageTitle('auth.signInTitle');
  const { signInWithPassword, signInWithGoogle, authAvailable } = useAuth();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [serverError, setServerError] = useState<string | null>(null);
  const next = safeInternalPath(params.get('next'), '/');

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: '', password: '' },
  });

  const onSubmit = form.handleSubmit(async (values) => {
    setServerError(null);
    try {
      const profile = await signInWithPassword(values.email.trim().toLowerCase(), values.password);
      const destination = profile.role === 'admin' ? '/admin' : next;
      void navigate(destination, { replace: true });
    } catch (error) {
      setServerError(authErrorMessage(error, 'We could not sign you in. Please try again.'));
    }
  });

  return (
    <div className="container max-w-md py-8">
      <h1 className="text-2xl font-extrabold tracking-tight">Welcome back</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Sign in to track orders, use your wallet and refer friends.
      </p>

      {!authAvailable && (
        <p className="mt-4 rounded-xl bg-warning-soft p-3 text-sm text-warning" role="alert">
          Sign-in is not configured for this build. Please call the store to place an order.
        </p>
      )}

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
          <Input
            id="email"
            type="email"
            inputMode="email"
            autoComplete="email"
            placeholder="you@example.com"
            aria-invalid={Boolean(form.formState.errors.email)}
            {...form.register('email')}
          />
          {form.formState.errors.email && (
            <p className="mt-1 text-xs text-primary-700">{form.formState.errors.email.message}</p>
          )}
        </div>

        <div>
          <label htmlFor="password" className="mb-1 block text-sm font-semibold">
            Password
          </label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            aria-invalid={Boolean(form.formState.errors.password)}
            {...form.register('password')}
          />
          {form.formState.errors.password && (
            <p className="mt-1 text-xs text-primary-700">
              {form.formState.errors.password.message}
            </p>
          )}
        </div>

        {serverError && (
          <p className="rounded-lg bg-primary-50 p-3 text-sm text-primary-900" role="alert">
            {serverError}
          </p>
        )}

        <Button type="submit" size="lg" className="w-full" disabled={form.formState.isSubmitting}>
          <LogIn aria-hidden="true" />
          {form.formState.isSubmitting ? 'Signing in…' : 'Sign in'}
        </Button>
      </form>

      <div className="mt-4 flex flex-col gap-2">
        <Button
          type="button"
          variant="outline"
          size="lg"
          onClick={() =>
            void signInWithGoogle(next).catch((error) =>
              setServerError(authErrorMessage(error, 'Google sign-in failed. Please try again.')),
            )
          }
          disabled={!authAvailable}
        >
          Continue with Google
        </Button>
        <Link to="/forgot-password" className="text-center text-sm font-medium text-primary-700">
          Forgot your password?
        </Link>
      </div>

      <p className="mt-6 text-center text-sm text-muted-foreground">
        New to MSG Store?{' '}
        <Link to="/sign-up" className="font-semibold text-primary-700">
          Create an account
        </Link>
      </p>
      <div className="mt-6 text-center">
        <CallStoreButton />
      </div>
    </div>
  );
}
