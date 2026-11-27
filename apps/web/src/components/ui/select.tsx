import { ChevronDown } from 'lucide-react';
import * as React from 'react';

import { cn } from '@/lib/utils';

/**
 * A native `<select>`. On a phone that means the platform picker — which the
 * owner can drive one-handed — instead of a custom listbox to maintain.
 */
export const Select = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(({ className, children, ...props }, ref) => (
  <div className="relative">
    <select
      ref={ref}
      className={cn(
        'min-h-touch w-full appearance-none rounded-xl border border-input bg-background py-2 pl-3 pr-9 text-base',
        'disabled:cursor-not-allowed disabled:opacity-50 focus-visible:border-primary',
        className,
      )}
      {...props}
    >
      {children}
    </select>
    <ChevronDown
      className="pointer-events-none absolute right-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
      aria-hidden="true"
    />
  </div>
));
Select.displayName = 'Select';
