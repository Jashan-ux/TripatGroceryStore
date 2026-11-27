import { cn } from '@/lib/utils';

/** Shimmering placeholder. `aria-hidden` so screen readers skip the noise. */
export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden="true" className={cn('skeleton h-4 w-full', className)} {...props} />;
}

export function ProductCardSkeleton() {
  return (
    <div className="card-elev flex flex-col gap-3 p-3" aria-hidden="true">
      <Skeleton className="aspect-square w-full rounded-lg" />
      <Skeleton className="h-3.5 w-4/5" />
      <Skeleton className="h-3 w-1/3" />
      <div className="flex items-center justify-between gap-2">
        <Skeleton className="h-4 w-16" />
        <Skeleton className="h-9 w-16 rounded-xl" />
      </div>
    </div>
  );
}

export function ProductRailSkeleton({ count = 4 }: { count?: number }) {
  return (
    <div className="rail" aria-hidden="true">
      {Array.from({ length: count }).map((_, index) => (
        <div key={index} className="w-[46%] xs:w-[44%] sm:w-[30%] lg:w-[23%]">
          <ProductCardSkeleton />
        </div>
      ))}
    </div>
  );
}
