import type { ProductAdminOut } from '@tripat/api-client';
import { useState } from 'react';

import {
  useAdminProducts,
  useUpdateProductStock,
  useUpdateVariantStock,
} from '@/admin/adminCatalogue';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { usePageTitle } from '@/hooks/usePageTitle';
import { cn } from '@/lib/utils';

type StockFilter = 'all' | 'low' | 'out';

/** Stock count workspace; each row writes through an audited, row-locked API. */
export function AdminInventoryPage() {
  usePageTitle(undefined, 'Inventory · Admin');
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState<StockFilter>('all');
  const [page, setPage] = useState(1);
  const products = useAdminProducts({
    q: query,
    categoryId: '',
    lowStock: filter === 'low',
    outOfStock: filter === 'out',
    page,
  });
  const items = products.data?.items ?? [];

  return (
    <div className="container max-w-4xl space-y-4 py-5 pb-nav-safe md:pb-8">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <div>
          <h1 className="text-xl font-extrabold tracking-tight">Inventory</h1>
          <p className="text-xs text-muted-foreground">
            Count stock by product or pack. Every saved count is audit logged.
          </p>
        </div>
        <p className="text-xs text-muted-foreground">
          {products.data
            ? `${products.data.total} product${products.data.total === 1 ? '' : 's'}`
            : 'Loading…'}
        </p>
      </header>

      <label htmlFor="inventory-search" className="sr-only">
        Search inventory
      </label>
      <Input
        id="inventory-search"
        type="search"
        placeholder="Search products"
        value={query}
        onChange={(event) => {
          setQuery(event.target.value);
          setPage(1);
        }}
      />

      <div className="flex flex-wrap gap-2" role="group" aria-label="Inventory stock filter">
        {(
          [
            ['all', 'All stock'],
            ['low', 'Low stock'],
            ['out', 'Out of stock'],
          ] as const
        ).map(([value, label]) => (
          <Button
            key={value}
            size="sm"
            variant={filter === value ? 'secondary' : 'outline'}
            aria-pressed={filter === value}
            onClick={() => {
              setFilter(value);
              setPage(1);
            }}
          >
            {label}
          </Button>
        ))}
      </div>

      {products.isPending ? (
        <div className="space-y-2" role="status" aria-live="polite">
          <span className="sr-only">Loading inventory</span>
          {Array.from({ length: 3 }).map((_, index) => (
            <Skeleton key={index} className="h-28 w-full rounded-xl" />
          ))}
        </div>
      ) : products.isError ? (
        <div className="rounded-xl border border-border bg-card p-4 text-sm" role="alert">
          <p className="font-semibold">Could not load inventory</p>
          <p className="text-muted-foreground">{products.error.message}</p>
          <Button
            size="sm"
            variant="outline"
            className="mt-2"
            onClick={() => void products.refetch()}
          >
            Try again
          </Button>
        </div>
      ) : items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
          {filter === 'all'
            ? 'No products match this search.'
            : filter === 'low'
              ? 'No low-stock products right now.'
              : 'No products are out of stock.'}
        </p>
      ) : (
        <ul className="space-y-3">
          {items.map((product) => (
            <li key={product.id}>
              <ProductInventoryCard product={product} />
            </li>
          ))}
        </ul>
      )}

      {products.data && products.data.total_pages > 1 && (
        <nav className="flex items-center justify-between gap-3" aria-label="Inventory pages">
          <Button
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((current) => current - 1)}
          >
            Previous
          </Button>
          <span className="text-xs text-muted-foreground">
            Page {products.data.page} of {products.data.total_pages}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= products.data.total_pages}
            onClick={() => setPage((current) => current + 1)}
          >
            Next
          </Button>
        </nav>
      )}
    </div>
  );
}

function ProductInventoryCard({ product }: { product: ProductAdminOut }) {
  const activeVariants = (product.variants ?? []).filter((variant) => variant.is_active);
  const variantStock = activeVariants.length > 0;

  return (
    <article className="rounded-xl border border-border bg-card p-3">
      <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="truncate text-sm font-bold">{product.name}</h2>
          <p className="text-xs text-muted-foreground">
            {product.category_name} · {product.unit_label}
          </p>
        </div>
        <span
          className={cn(
            'rounded-full px-2 py-1 text-xs font-semibold tabular-nums',
            product.available_stock <= 0
              ? 'bg-destructive/10 text-destructive'
              : product.available_stock <= product.low_stock_threshold
                ? 'bg-warning-soft text-warning'
                : 'bg-success-soft text-success',
          )}
        >
          {product.available_stock} available
        </span>
      </div>

      {variantStock ? (
        <div className="space-y-2 border-t border-border pt-2">
          {activeVariants.map((variant) => (
            <StockEditor
              key={variant.id}
              productId={product.id}
              productName={product.name}
              variantId={variant.id}
              variantLabel={variant.label}
              currentStock={variant.stock}
              threshold={product.low_stock_threshold}
            />
          ))}
        </div>
      ) : (
        <div className="border-t border-border pt-2">
          <StockEditor
            key={product.id}
            productId={product.id}
            productName={product.name}
            currentStock={product.stock}
            threshold={product.low_stock_threshold}
          />
        </div>
      )}
    </article>
  );
}

function StockEditor({
  productId,
  productName,
  variantId,
  variantLabel,
  currentStock,
  threshold,
}: {
  productId: string;
  productName: string;
  variantId?: string;
  variantLabel?: string;
  currentStock: number;
  threshold: number;
}) {
  const [stock, setStock] = useState(String(currentStock));
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const productMutation = useUpdateProductStock();
  const variantMutation = useUpdateVariantStock();
  const pending = productMutation.isPending || variantMutation.isPending;
  const numericStock = Number(stock);
  const itemName = variantLabel ? `${productName} (${variantLabel})` : productName;

  const save = () => {
    if (!Number.isInteger(numericStock) || numericStock < 0 || numericStock > 1_000_000) return;
    if (
      numericStock < currentStock &&
      !window.confirm(`Set ${itemName} stock to ${numericStock}? This reduces sellable quantity.`)
    ) {
      return;
    }
    setNotice(null);
    setError(null);
    const onSuccess = (saved: ProductAdminOut) => {
      const savedCount = variantId
        ? ((saved.variants ?? []).find((variant) => variant.id === variantId)?.stock ??
          numericStock)
        : saved.stock;
      setStock(String(savedCount));
      setNotice(`${itemName} stock saved.`);
    };
    const onError = (mutationError: Error) => setError(mutationError.message);
    if (variantId) {
      variantMutation.mutate(
        { productId, variantId, stock: numericStock, note: 'Inventory count adjustment' },
        { onSuccess, onError },
      );
    } else {
      productMutation.mutate(
        { productId, stock: numericStock, note: 'Inventory count adjustment' },
        { onSuccess, onError },
      );
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <label className="min-w-0 flex-1 text-xs font-semibold">
        {variantLabel ? `Pack ${variantLabel}` : 'Product stock'}
        <Input
          className="mt-1 max-w-36"
          type="number"
          min={0}
          max={1_000_000}
          step={1}
          inputMode="numeric"
          aria-label={`${itemName} stock count`}
          value={stock}
          onChange={(event) => setStock(event.target.value)}
        />
      </label>
      <span className="text-xs text-muted-foreground">Alert at {threshold}</span>
      <Button
        size="sm"
        variant="outline"
        onClick={save}
        disabled={
          pending ||
          !stock.trim() ||
          numericStock === currentStock ||
          !Number.isInteger(numericStock) ||
          numericStock < 0
        }
      >
        {pending ? 'Saving…' : 'Save count'}
      </Button>
      {notice && (
        <p role="status" className="w-full text-xs text-success">
          {notice}
        </p>
      )}
      {error && (
        <p role="alert" className="w-full text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  );
}
