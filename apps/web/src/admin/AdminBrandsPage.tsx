import { Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';

import { useAdminBrands, useCreateBrand, useDeleteBrand } from '@/admin/adminCatalogue';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { usePageTitle } from '@/hooks/usePageTitle';

/**
 * Brands.
 *
 * A brand is only deletable while nothing points at it — so the count next to
 * each name is not decoration, it is the reason a delete button is disabled.
 */
export function AdminBrandsPage() {
  usePageTitle(undefined, 'Brands · Admin');
  const brands = useAdminBrands();
  const create = useCreateBrand();
  const remove = useDeleteBrand();
  const [name, setName] = useState('');
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  return (
    <div className="container max-w-3xl space-y-4 py-5 pb-nav-safe md:pb-8">
      <h1 className="text-xl font-extrabold tracking-tight">Brands</h1>

      <div className="flex flex-wrap items-end gap-2 rounded-xl border border-border bg-card p-3">
        <label className="min-w-40 flex-1 text-xs font-semibold" htmlFor="brand-name">
          Brand name
          <Input
            id="brand-name"
            className="mt-1"
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Amul"
          />
        </label>
        <Button
          disabled={create.isPending || !name.trim()}
          onClick={() => {
            setError(null);
            create.mutate(
              { name: name.trim() },
              {
                onSuccess: (brand) => {
                  setNotice(`${brand.name} added.`);
                  setName('');
                },
                onError: (err) => setError(err.message),
              },
            );
          }}
        >
          <Plus aria-hidden="true" /> Add brand
        </Button>
      </div>

      {notice && (
        <p
          role="status"
          className="rounded-lg bg-success-soft p-2.5 text-sm font-medium text-success"
        >
          {notice}
        </p>
      )}
      {error && (
        <p
          role="alert"
          className="rounded-lg bg-warning-soft p-2.5 text-sm font-medium text-warning"
        >
          {error}
        </p>
      )}

      {brands.isPending ? (
        <Skeleton className="h-48 w-full rounded-xl" />
      ) : (
        <ul className="divide-y divide-border rounded-xl border border-border bg-card">
          {(brands.data?.brands ?? []).map((brand) => (
            <li key={brand.id} className="flex items-center gap-2 px-3 py-2.5">
              <p className="font-semibold">{brand.name}</p>
              <p className="text-xs text-muted-foreground">
                {brand.product_count} product{brand.product_count === 1 ? '' : 's'}
              </p>
              <Button
                size="icon"
                variant="ghost"
                className="ml-auto"
                aria-label={`Delete ${brand.name}`}
                disabled={remove.isPending || brand.product_count > 0}
                title={
                  brand.product_count > 0
                    ? 'Move its products to another brand first'
                    : `Delete ${brand.name}`
                }
                onClick={() =>
                  remove.mutate(brand.id, {
                    onSuccess: () => setNotice(`${brand.name} deleted.`),
                    onError: (err) => setError(err.message),
                  })
                }
              >
                <Trash2 aria-hidden="true" />
              </Button>
            </li>
          ))}
          {(brands.data?.brands ?? []).length === 0 && (
            <li className="px-3 py-6 text-center text-sm text-muted-foreground">
              No brands yet. Add the first one above.
            </li>
          )}
        </ul>
      )}
    </div>
  );
}
