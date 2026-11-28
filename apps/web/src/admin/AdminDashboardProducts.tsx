import type { ProductAdminOut } from '@tripat/api-client';
import { Check, ChevronLeft, ChevronRight, Pencil, Search, X } from 'lucide-react';
import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';

import { useAdminProducts, useUpdateProduct } from '@/admin/adminCatalogue';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { formatPaise } from '@/lib/utils';

interface ProductDraft {
  name: string;
  unit: string;
  price: string;
  mrp: string;
  isActive: boolean;
}

function draftFor(product: ProductAdminOut): ProductDraft {
  return {
    name: product.name,
    unit: product.unit_label,
    price: (product.price_paise / 100).toFixed(2),
    mrp: (product.mrp_paise / 100).toFixed(2),
    isActive: product.is_active,
  };
}

function toPaise(value: string): number | null {
  const amount = Number(value);
  return Number.isFinite(amount) && amount >= 0 ? Math.round(amount * 100) : null;
}

/**
 * Small, audited catalogue editor placed on the merchant dashboard. It edits
 * product details without leaving the dashboard; inventory counts stay in the
 * dedicated inventory workspace so stock changes retain their audit note.
 */
export function AdminDashboardProducts() {
  const [searchInput, setSearchInput] = useState('');
  const [query, setQuery] = useState('');
  const [page, setPage] = useState(1);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draft, setDraft] = useState<ProductDraft | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const products = useAdminProducts({ q: query, categoryId: '', lowStock: false, page });
  const update = useUpdateProduct();

  const startEdit = (product: ProductAdminOut) => {
    setEditingId(product.id);
    setDraft(draftFor(product));
    setNotice(null);
    setError(null);
  };

  const cancelEdit = () => {
    setEditingId(null);
    setDraft(null);
    setError(null);
  };

  const search = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setQuery(searchInput.trim());
    setPage(1);
    cancelEdit();
  };

  const save = (product: ProductAdminOut) => {
    if (!draft) return;
    const pricePaise = toPaise(draft.price);
    const mrpPaise = toPaise(draft.mrp);
    const name = draft.name.trim();
    const unit = draft.unit.trim();
    if (!name || pricePaise === null || mrpPaise === null) {
      setError('Enter a product name and valid prices in rupees.');
      return;
    }
    if (mrpPaise > 0 && pricePaise > mrpPaise) {
      setError('Selling price cannot be higher than MRP.');
      return;
    }

    setError(null);
    setNotice(null);
    update.mutate(
      {
        id: product.id,
        name,
        unit_label: unit,
        price_paise: pricePaise,
        mrp_paise: mrpPaise,
        is_active: draft.isActive,
      },
      {
        onSuccess: (saved) => {
          setNotice(`${saved.name} saved.`);
          setEditingId(null);
          setDraft(null);
        },
        onError: (mutationError) => setError(mutationError.message),
      },
    );
  };

  const data = products.data;
  const items = data?.items ?? [];

  return (
    <Card aria-labelledby="dashboard-product-manager-title" className="overflow-hidden">
      <CardHeader className="gap-3 border-b border-border/70 bg-card sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-primary">
            Catalogue desk
          </p>
          <CardTitle id="dashboard-product-manager-title" className="mt-1 text-lg">
            Edit products here
          </CardTitle>
          <p className="mt-1 text-sm text-muted-foreground">
            Update names, prices, units, or storefront visibility without leaving your dashboard.
          </p>
        </div>
        <Link
          to="/admin/products"
          className="inline-flex min-h-touch shrink-0 items-center text-sm font-semibold text-primary hover:underline"
        >
          Full catalogue <span className="sr-only">and bulk tools</span>
        </Link>
      </CardHeader>
      <CardContent className="space-y-3 pt-4">
        <form className="flex flex-col gap-2 sm:flex-row" onSubmit={search} role="search">
          <label className="sr-only" htmlFor="dashboard-product-search">
            Find a product to edit
          </label>
          <div className="relative min-w-0 flex-1">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              id="dashboard-product-search"
              type="search"
              className="pl-9"
              placeholder="Search products by name"
              value={searchInput}
              onChange={(event) => setSearchInput(event.target.value)}
            />
          </div>
          <Button type="submit" variant="outline" size="sm">
            Search catalogue
          </Button>
        </form>

        {notice && (
          <p role="status" className="rounded-lg bg-success-soft px-3 py-2 text-sm text-success">
            {notice}
          </p>
        )}
        {error && (
          <p role="alert" className="rounded-lg bg-warning-soft px-3 py-2 text-sm text-warning">
            {error}
          </p>
        )}

        {products.isPending ? (
          <div className="space-y-2" role="status" aria-live="polite">
            <span className="sr-only">Loading products</span>
            {Array.from({ length: 3 }).map((_, index) => (
              <Skeleton key={index} className="h-20 rounded-xl" />
            ))}
          </div>
        ) : products.isError ? (
          <div className="rounded-xl border border-border p-4 text-sm" role="alert">
            <p className="font-semibold">Could not load products</p>
            <p className="mt-1 text-muted-foreground">{products.error.message}</p>
            <Button
              className="mt-2"
              size="sm"
              variant="outline"
              onClick={() => void products.refetch()}
            >
              Try again
            </Button>
          </div>
        ) : items.length === 0 ? (
          <p className="rounded-xl border border-dashed border-border p-5 text-center text-sm text-muted-foreground">
            {query ? 'No products match that search.' : 'No products to edit yet.'}
          </p>
        ) : (
          <ul className="divide-y divide-border/70 rounded-xl border border-border/70">
            {items.map((product) => (
              <DashboardProductRow
                key={product.id}
                product={product}
                editing={editingId === product.id}
                draft={editingId === product.id ? draft : null}
                saving={update.isPending}
                onStartEdit={() => startEdit(product)}
                onCancel={cancelEdit}
                onDraftChange={setDraft}
                onSave={() => save(product)}
              />
            ))}
          </ul>
        )}

        {data && data.total_pages > 1 && (
          <nav
            className="flex items-center justify-between gap-3"
            aria-label="Dashboard product pages"
          >
            <Button
              variant="outline"
              size="sm"
              disabled={page <= 1}
              onClick={() => {
                setPage((current) => current - 1);
                cancelEdit();
              }}
            >
              <ChevronLeft aria-hidden="true" /> Previous
            </Button>
            <span className="text-xs text-muted-foreground">
              Page {data.page} of {data.total_pages} · {data.total} products
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={page >= data.total_pages}
              onClick={() => {
                setPage((current) => current + 1);
                cancelEdit();
              }}
            >
              Next <ChevronRight aria-hidden="true" />
            </Button>
          </nav>
        )}

        <p className="text-xs text-muted-foreground">
          Stock counts are edited in{' '}
          <Link to="/admin/inventory" className="font-semibold text-primary hover:underline">
            Inventory
          </Link>{' '}
          so every count adjustment remains separately auditable.
        </p>
      </CardContent>
    </Card>
  );
}

function DashboardProductRow({
  product,
  editing,
  draft,
  saving,
  onStartEdit,
  onCancel,
  onDraftChange,
  onSave,
}: {
  product: ProductAdminOut;
  editing: boolean;
  draft: ProductDraft | null;
  saving: boolean;
  onStartEdit: () => void;
  onCancel: () => void;
  onDraftChange: (draft: ProductDraft | null) => void;
  onSave: () => void;
}) {
  const activeVariants = (product.variants ?? []).filter((variant) => variant.is_active);

  return (
    <li className="p-3 sm:p-4">
      {!editing || !draft ? (
        <div className="flex flex-wrap items-center gap-3">
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-bold">{product.name}</p>
            <p className="truncate text-xs text-muted-foreground">
              {product.category_name} · {product.unit_label || 'No unit'}
              {activeVariants.length > 0 ? ` · ${activeVariants.length} active pack(s)` : ''}
            </p>
          </div>
          <div className="flex items-center gap-3">
            <div className="text-right">
              <p className="text-sm font-bold tabular-nums">{formatPaise(product.price_paise)}</p>
              <p className="text-xs text-muted-foreground">
                {product.is_active ? `${product.available_stock} available` : 'Hidden'}
              </p>
            </div>
            <Badge tone={product.is_active ? 'success' : 'neutral'}>
              {product.is_active ? 'Live' : 'Hidden'}
            </Badge>
            <Button
              size="sm"
              variant="outline"
              aria-label={`Edit ${product.name} on dashboard`}
              onClick={onStartEdit}
            >
              <Pencil aria-hidden="true" /> Edit
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="flex items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-bold">Edit product</p>
              <p className="truncate text-xs text-muted-foreground">{product.category_name}</p>
            </div>
            <Button
              size="icon"
              variant="ghost"
              aria-label={`Cancel editing ${product.name}`}
              onClick={onCancel}
              disabled={saving}
            >
              <X aria-hidden="true" />
            </Button>
          </div>
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
            <label
              className="text-xs font-semibold sm:col-span-2"
              htmlFor={`dash-name-${product.id}`}
            >
              Product name
              <Input
                id={`dash-name-${product.id}`}
                className="mt-1"
                maxLength={200}
                value={draft.name}
                onChange={(event) => onDraftChange({ ...draft, name: event.target.value })}
              />
            </label>
            <label className="text-xs font-semibold" htmlFor={`dash-price-${product.id}`}>
              Selling price (₹)
              <Input
                id={`dash-price-${product.id}`}
                className="mt-1"
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                value={draft.price}
                onChange={(event) => onDraftChange({ ...draft, price: event.target.value })}
              />
            </label>
            <label className="text-xs font-semibold" htmlFor={`dash-mrp-${product.id}`}>
              MRP (₹)
              <Input
                id={`dash-mrp-${product.id}`}
                className="mt-1"
                type="number"
                min="0"
                step="0.01"
                inputMode="decimal"
                value={draft.mrp}
                onChange={(event) => onDraftChange({ ...draft, mrp: event.target.value })}
              />
            </label>
            <label className="text-xs font-semibold" htmlFor={`dash-unit-${product.id}`}>
              Unit label
              <Input
                id={`dash-unit-${product.id}`}
                className="mt-1"
                maxLength={40}
                value={draft.unit}
                onChange={(event) => onDraftChange({ ...draft, unit: event.target.value })}
              />
            </label>
            <label className="flex min-h-touch items-center gap-2 self-end rounded-xl border border-border px-3 text-sm font-semibold">
              <input
                type="checkbox"
                className="size-4 accent-primary"
                checked={draft.isActive}
                onChange={(event) => onDraftChange({ ...draft, isActive: event.target.checked })}
              />
              Show on storefront
            </label>
          </div>
          {activeVariants.length > 0 && (
            <p className="text-xs text-muted-foreground">
              This quick edit changes product-level details only. Pack prices and pack stock are not
              changed here.
            </p>
          )}
          <div className="flex flex-wrap justify-end gap-2">
            <Button variant="ghost" size="sm" onClick={onCancel} disabled={saving}>
              Cancel
            </Button>
            <Button size="sm" onClick={onSave} disabled={saving || !draft.name.trim()}>
              <Check aria-hidden="true" /> {saving ? 'Saving…' : 'Save product'}
            </Button>
          </div>
        </div>
      )}
    </li>
  );
}
