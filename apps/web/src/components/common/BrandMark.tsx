import { cn } from '@/lib/utils';

interface BrandMarkProps {
  className?: string;
  /** Decorative when the wordmark sits next to it; otherwise provide a label. */
  decorative?: boolean;
}

/**
 * The store logo. The owner supplies the final artwork as
 * `public/brand/logo.png`; until then the shipped SVG monogram is used, so no
 * view ever renders a broken image.
 */
export function BrandMark({ className, decorative = false }: BrandMarkProps) {
  return (
    <img
      src="/brand/logo.svg"
      width={110}
      height={110}
      alt={decorative ? '' : 'Tripat Pansari · MSG Store logo'}
      aria-hidden={decorative || undefined}
      className={cn('size-11 shrink-0 rounded-full object-contain sm:size-12', className)}
      decoding="async"
    />
  );
}

export function Wordmark({ className }: { className?: string }) {
  return (
    <span className={cn('flex flex-col leading-none', className)}>
      <span className="text-[17px] font-extrabold tracking-tight text-primary sm:text-lg">
        Tripat Pansari
      </span>
      <span className="mt-0.5 text-[10px] font-semibold uppercase tracking-[0.22em] text-muted-foreground sm:text-[11px]">
        MSG Store
      </span>
    </span>
  );
}
