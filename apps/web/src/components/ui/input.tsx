import * as React from 'react';

import { cn } from '@/lib/utils';

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, type = 'text', ...props }, ref) => (
  <input
    ref={ref}
    type={type}
    className={cn(
      'flex min-h-touch w-full rounded-xl border border-input bg-background px-3 py-2 text-base',
      'placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50',
      'focus-visible:border-primary',
      className,
    )}
    {...props}
  />
));
Input.displayName = 'Input';
