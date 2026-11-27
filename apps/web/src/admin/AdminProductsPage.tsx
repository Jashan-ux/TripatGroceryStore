import type { ProductAdminOut } from '@tripat/api-client';
import { Eye, EyeOff, Pencil, Plus, Search, Trash2, Upload } from 'lucide-react';
import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';

import {
  useAdminBrands,
  useAdminCategories,
  useAdminProduct,
  useAdminProducts,
  useBulkImport,
  useCreateProduct,
  useDeleteProduct,
  useUpdateProduct,
  useUploadImage,
  type ProductDraft,
} from '@/admin/adminCatalogue';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeaderCell,
  TableRow,
} from '@/components/ui/table';
import { Textarea } from '@/components/ui/textarea';
import { usePageTitle } from '@/hooks/usePageTitle';
import { cn, formatPaise } from '@/lib/utils';

/** Rupees in the form, paise in the database — the conversion happens once, here. */
function toPaise(value: string): number {
  const rupees = Number(value.replace(/[^\d.]/g, ''));
  return Number.isFinite(rupees) ? Math.round(rupees * 100) : 0;
}

function toRupees(paise: number): string {
  return (paise / 100).toFixed(2);
}

interface DraftState {
  name: string;
  categoryId: string;
  brandId: string;
  price: string;
  mrp: string;
  stock: string;
  unit: string;
  imageUrl: string;
}

const EMPTY_DRAFT: DraftState = {
  name: '',
  categoryId: '',
  brandId: '',
  price: '',
  mrp: '',
  stock: '0',
  unit: '1 kg',
  imageUrl: '',
};

/**
 * The catalogue screen.
 *
 * Three ways in, in order of how often the owner needs them: the inline row
 * (add one item to a shelf), the edit dialog (price or stock changed), and the
 * bulk sheet (a new supplier's price list). The bulk sheet always previews before
 * it writes — one bad row means nothing is saved, and the preview says which line.
 */
export function AdminProductsPage() {
  usePageTitle(undefined, 'Products · Admin');
  const [q, setQ] = useState('');
  const [categoryId, setCategoryId] = useState('');
  const [lowStock, setLowStock] = useState(false);
  const [page, setPage] = useState(1);
  const [draft, setDraft] = useState<DraftState>(EMPTY_DRAFT);
  const [editing, setEditing] = useState<ProductAdminOut | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();
  const editProductId = searchParams.get('edit');

  const deepLinkedProduct = useAdminProduct(editProductId);
  const activeEditing = editProductId ? (deepLinkedProduct.data ?? null) : editing;

  const categories = useAdminCategories();
  const brands = useAdminBrands();
  const products = useAdminProducts({ q, categoryId, lowStock, page });
  const create = useCreateProduct();
  const update = useUpdateProduct();
  const remove = useDeleteProduct();
  const upload = useUploadImage();

  const categoryOptions = categories.data?.categories ?? [];
  const data = products.data;

  const reset = () => setDraft({ ...EMPTY_DRAFT, categoryId });

  const add = () => {
    setError(null);
    setNotice(null);
    create.mutate(
      {
        name: draft.name.trim(),
        category_id: draft.categoryId || categoryId,
        brand_id: draft.brandId || null,
        price_paise: toPaise(draft.price),
        mrp_paise: draft.mrp ? toPaise(draft.mrp) : toPaise(draft.price),
        stock: Number(draft.stock) || 0,
        unit_label: draft.unit.trim() || undefined,
        images: draft.imageUrl.trim() ? [draft.imageUrl.trim()] : [],
      },
      {
        onSuccess: (product) => {
          setNotice(`${product.name} is on the storefront now.`);
          reset();
        },
        onError: (err) => setError(err.message),
      },
    );
  };

  const del = (product: ProductAdminOut) => {
    setError(null);
    setNotice(null);
    remove.mutate(product.id, {
      onSuccess: (result) => setNotice(result.message),
      onError: (err) => setError(err.message),
    });
  };

  return (
    <div className="container max-w-5xl space-y-4 py-5 pb-nav-safe md:pb-8">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h1 className="text-xl font-extrabold tracking-tight">Products</h1>
        <p className="text-xs text-muted-foreground">
          {data ? `${data.total} product${data.total === 1 ? '' : 's'}` : 'Loading…'}
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <label className="min-w-40 flex-1 text-xs font-semibold" htmlFor="search">
          Search
          <div className="relative mt-1">
            <Search
              className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              aria-hidden="true"
            />
            <Input
              id="search"
              className="pl-9"
              value={q}
              onChange={(event) => {
                setQ(event.target.value);
                setPage(1);
              }}
              placeholder="Name, brand or item"
            />
          </div>
        </label>
        <label className="min-w-36 text-xs font-semibold" htmlFor="shelf">
          Shelf
          <Select
            id="shelf"
            className="mt-1"
            value={categoryId}
            onChange={(event) => {
              setCategoryId(event.target.value);
              setPage(1);
            }}
          >
            <option value="">Every category</option>
            {categoryOptions.map((category) => (
              <option key={category.id} value={category.id}>
                {category.parent_name
                  ? `${category.parent_name} › ${category.name}`
                  : category.name}
              </option>
            ))}
          </Select>
        </label>
        <label className="flex min-h-touch items-center gap-2 text-sm font-semibold">
          <input
            type="checkbox"
            className="size-4"
            checked={lowStock}
            onChange={(event) => {
              setLowStock(event.target.checked);
              setPage(1);
            }}
          />
          Low stock only
        </label>
        <Button variant="outline" onClick={() => setBulkOpen(true)}>
          <Upload aria-hidden="true" /> Bulk add
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

      {/* Inline add: the first row of every shift is "we got this in today". */}
      <section
        aria-labelledby="inline-add"
        className="rounded-xl border border-dashed border-border bg-card p-3"
      >
        <h2 id="inline-add" className="flex items-center gap-1.5 text-sm font-bold">
          <Plus className="size-4 text-primary" aria-hidden="true" /> Add one product
        </h2>
        <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          <label className="text-xs font-semibold" htmlFor="name">
            Name
            <Input
              id="name"
              className="mt-1"
              value={draft.name}
              onChange={(event) => setDraft({ ...draft, name: event.target.value })}
              placeholder="Ghee 1 L tin"
            />
          </label>
          <label className="text-xs font-semibold" htmlFor="shelf-2">
            Shelf
            <Select
              id="shelf-2"
              className="mt-1"
              value={draft.categoryId || categoryId}
              onChange={(event) => setDraft({ ...draft, categoryId: event.target.value })}
            >
              <option value="">Choose…</option>
              {categoryOptions.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.parent_name
                    ? `${category.parent_name} › ${category.name}`
                    : category.name}
                </option>
              ))}
            </Select>
          </label>
          <label className="text-xs font-semibold" htmlFor="price">
            Price (₹)
            <Input
              id="price"
              className="mt-1"
              inputMode="decimal"
              value={draft.price}
              onChange={(event) => setDraft({ ...draft, price: event.target.value })}
              placeholder="640"
            />
          </label>
          <label className="text-xs font-semibold" htmlFor="stock">
            Stock
            <Input
              id="stock"
              className="mt-1"
              inputMode="numeric"
              value={draft.stock}
              onChange={(event) => setDraft({ ...draft, stock: event.target.value })}
            />
          </label>
          <label className="text-xs font-semibold" htmlFor="mrp-optional">
            MRP (₹, optional)
            <Input
              id="mrp-optional"
              className="mt-1"
              inputMode="decimal"
              value={draft.mrp}
              onChange={(event) => setDraft({ ...draft, mrp: event.target.value })}
            />
          </label>
          <label className="text-xs font-semibold" htmlFor="unit">
            Unit
            <Input
              id="unit"
              className="mt-1"
              value={draft.unit}
              onChange={(event) => setDraft({ ...draft, unit: event.target.value })}
            />
          </label>
          <label className="text-xs font-semibold" htmlFor="brand">
            Brand
            <Select
              id="brand"
              className="mt-1"
              value={draft.brandId}
              onChange={(event) => setDraft({ ...draft, brandId: event.target.value })}
            >
              <option value="">No brand</option>
              {(brands.data?.brands ?? []).map((brand) => (
                <option key={brand.id} value={brand.id}>
                  {brand.name}
                </option>
              ))}
            </Select>
          </label>
          <label className="text-xs font-semibold" htmlFor="image-url">
            Image URL
            <Input
              id="image-url"
              className="mt-1"
              value={draft.imageUrl}
              onChange={(event) => setDraft({ ...draft, imageUrl: event.target.value })}
              placeholder="https://…"
            />
          </label>
        </div>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <Button onClick={add} disabled={create.isPending || !draft.name.trim() || !draft.price}>
            {create.isPending ? 'Adding…' : 'Add product'}
          </Button>
          <p className="text-xs text-muted-foreground">
            It appears on the storefront immediately — no cache to clear.
          </p>
        </div>
      </section>

      {products.isPending ? (
        <Skeleton className="h-64 w-full rounded-xl" role="status" />
      ) : products.isError ? (
        <div className="rounded-xl border border-border bg-card p-4 text-sm" role="alert">
          <p className="font-semibold">Could not load products</p>
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
      ) : !data || data.items.length === 0 ? (
        <p className="rounded-xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
          No products match. Clear the filters or add the first one above.
        </p>
      ) : (
        <Table>
          <TableHead>
            <TableRow>
              <TableHeaderCell>Product</TableHeaderCell>
              <TableHeaderCell>Shelf</TableHeaderCell>
              <TableHeaderCell className="text-right">Price</TableHeaderCell>
              <TableHeaderCell className="text-right">Stock</TableHeaderCell>
              <TableHeaderCell className="text-right">Actions</TableHeaderCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {data.items.map((product) => (
              <TableRow key={product.id}>
                <TableCell>
                  <p className="font-semibold">{product.name}</p>
                  <p className="text-xs text-muted-foreground">
                    {product.unit_label}
                    {product.brand_name ? ` · ${product.brand_name}` : ''}
                    {product.is_active ? '' : ' · hidden'}
                  </p>
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">
                  {product.category_name}
                </TableCell>
                <TableCell className="text-right font-semibold">
                  {formatPaise(product.price_paise)}
                </TableCell>
                <TableCell
                  className={cn(
                    'text-right',
                    product.available_stock <= product.low_stock_threshold &&
                      'font-bold text-warning',
                  )}
                >
                  {product.available_stock}
                </TableCell>
                <TableCell>
                  <div className="flex justify-end gap-1">
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label={`Edit ${product.name}`}
                      onClick={() => setEditing(product)}
                    >
                      <Pencil aria-hidden="true" />
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label={`${product.is_active ? 'Hide' : 'Show'} ${product.name} on storefront`}
                      aria-pressed={product.is_active}
                      onClick={() => {
                        setError(null);
                        update.mutate(
                          { id: product.id, is_active: !product.is_active },
                          {
                            onSuccess: () =>
                              setNotice(
                                `${product.name} ${product.is_active ? 'hidden from' : 'shown on'} the storefront.`,
                              ),
                            onError: (mutationError) => setError(mutationError.message),
                          },
                        );
                      }}
                      disabled={update.isPending}
                    >
                      {product.is_active ? (
                        <EyeOff aria-hidden="true" />
                      ) : (
                        <Eye aria-hidden="true" />
                      )}
                    </Button>
                    <Button
                      size="icon"
                      variant="ghost"
                      aria-label={`Delete ${product.name}`}
                      onClick={() => del(product)}
                      disabled={remove.isPending}
                    >
                      <Trash2 aria-hidden="true" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}

      {data && data.total_pages > 1 && (
        <div className="flex items-center justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 1}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <p className="text-xs text-muted-foreground">
            Page {data.page} of {data.total_pages}
          </p>
          <Button
            variant="outline"
            size="sm"
            disabled={page >= data.total_pages}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}

      <EditProductDialog
        product={activeEditing}
        onClose={() => {
          setEditing(null);
          if (searchParams.has('edit')) {
            const next = new URLSearchParams(searchParams);
            next.delete('edit');
            setSearchParams(next, { replace: true });
          }
        }}
        onSave={(body) => {
          if (!activeEditing) return;
          setError(null);
          update.mutate(
            { id: activeEditing.id, ...body },
            {
              onSuccess: () => {
                setNotice(`${activeEditing.name} updated.`);
                setEditing(null);
              },
              onError: (err) => setError(err.message),
            },
          );
        }}
        saving={update.isPending}
        upload={upload}
      />

      <BulkDialog open={bulkOpen} onClose={() => setBulkOpen(false)} />
    </div>
  );
}

function EditProductDialog({
  product,
  onClose,
  onSave,
  saving,
  upload,
}: {
  product: ProductAdminOut | null;
  onClose: () => void;
  onSave: (body: Partial<ProductDraft>) => void;
  saving: boolean;
  upload: ReturnType<typeof useUploadImage>;
}) {
  // Remounted per product (`key`) so the inputs start from that row's values —
  // syncing props into state in an effect is what React now warns about.
  if (!product) return null;
  return (
    <Dialog open onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="w-[min(94vw,32rem)]">
        <DialogTitle>Edit {product.name}</DialogTitle>
        <DialogDescription>
          Saving here changes the storefront on the next page load.
        </DialogDescription>
        <EditProductForm product={product} onSave={onSave} saving={saving} upload={upload} />
      </DialogContent>
    </Dialog>
  );
}

function EditProductForm({
  product,
  onSave,
  saving,
  upload,
}: {
  product: ProductAdminOut;
  onSave: (body: Partial<ProductDraft>) => void;
  saving: boolean;
  upload: ReturnType<typeof useUploadImage>;
}) {
  const [name, setName] = useState(product.name);
  const [price, setPrice] = useState(toRupees(product.price_paise));
  const [mrp, setMrp] = useState(toRupees(product.mrp_paise));
  const [stock, setStock] = useState(String(product.stock));
  const [unit, setUnit] = useState(product.unit_label);
  const [image, setImage] = useState(product.images?.[0] ?? '');
  const [threshold, setThreshold] = useState(String(product.low_stock_threshold));

  return (
    <form
      className="mt-3 space-y-2"
      onSubmit={(event) => {
        event.preventDefault();
        onSave({
          name: name.trim(),
          price_paise: toPaise(price),
          mrp_paise: toPaise(mrp),
          stock: Number(stock) || 0,
          unit_label: unit.trim(),
          low_stock_threshold: Number(threshold) || 0,
          images: image.trim() ? [image.trim()] : [],
        });
      }}
    >
      <label className="block text-xs font-semibold" htmlFor="name-2">
        Name
        <Input
          id="name-2"
          className="mt-1"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </label>
      <div className="grid grid-cols-2 gap-2">
        <label className="text-xs font-semibold" htmlFor="price-2">
          Price (₹)
          <Input
            id="price-2"
            className="mt-1"
            inputMode="decimal"
            value={price}
            onChange={(event) => setPrice(event.target.value)}
          />
        </label>
        <label className="text-xs font-semibold" htmlFor="mrp">
          MRP (₹)
          <Input
            id="mrp"
            className="mt-1"
            inputMode="decimal"
            value={mrp}
            onChange={(event) => setMrp(event.target.value)}
          />
        </label>
        <label className="text-xs font-semibold" htmlFor="stock-2">
          Stock
          <Input
            id="stock-2"
            className="mt-1"
            inputMode="numeric"
            value={stock}
            onChange={(event) => setStock(event.target.value)}
          />
        </label>
        <label className="text-xs font-semibold" htmlFor="low-stock-alert-at">
          Low-stock alert at
          <Input
            id="low-stock-alert-at"
            className="mt-1"
            inputMode="numeric"
            value={threshold}
            onChange={(event) => setThreshold(event.target.value)}
          />
        </label>
      </div>
      <label className="block text-xs font-semibold" htmlFor="unit-2">
        Unit
        <Input
          id="unit-2"
          className="mt-1"
          value={unit}
          onChange={(event) => setUnit(event.target.value)}
        />
      </label>
      <label className="block text-xs font-semibold" htmlFor="image">
        Image
        <Input
          id="image"
          className="mt-1"
          value={image}
          onChange={(event) => setImage(event.target.value)}
          placeholder="https://…"
        />
      </label>
      <div className="flex flex-wrap items-center gap-2">
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          aria-label="Upload a photo"
          className="text-xs"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            upload.mutate(file, { onSuccess: (result) => setImage(result.url) });
          }}
        />
        {upload.isPending && <span className="text-xs text-muted-foreground">Uploading…</span>}
        {upload.isError && (
          <span className="text-xs font-semibold text-warning">{upload.error.message}</span>
        )}
      </div>
      <Button type="submit" disabled={saving} className="w-full">
        {saving ? 'Saving…' : 'Save changes'}
      </Button>
    </form>
  );
}

const SAMPLE_CSV = `name,category,price,unit,mrp,stock
Toor Dal 1 kg,${''},145.50,1 kg,160,20`;

function BulkDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [csv, setCsv] = useState(SAMPLE_CSV);
  const bulk = useBulkImport();
  if (!open) return null;
  const result = bulk.data;

  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogContent className="w-[min(96vw,44rem)]">
        <DialogTitle>Bulk add from a sheet</DialogTitle>
        <DialogDescription>
          Columns: name, category (slug), price, and optionally unit, mrp, stock, brand, image_url.
          Preview first — if one row is wrong, nothing is saved.
        </DialogDescription>
        <label className="mt-3 block text-xs font-semibold" htmlFor="paste-your-rows">
          Paste your rows
          <Textarea
            id="paste-your-rows"
            className="mt-1 font-mono text-xs"
            rows={7}
            value={csv}
            onChange={(event) => setCsv(event.target.value)}
          />
        </label>
        <div className="mt-2 flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={() => bulk.mutate({ csv, dry_run: true })}
            disabled={bulk.isPending}
          >
            Preview
          </Button>
          <Button
            onClick={() => bulk.mutate({ csv, dry_run: false })}
            disabled={bulk.isPending || !result?.valid || Boolean(result?.invalid)}
          >
            Save {result?.valid ? `${result.valid} product(s)` : 'all rows'}
          </Button>
          {bulk.isError && (
            <span className="text-xs font-semibold text-warning">{bulk.error.message}</span>
          )}
        </div>

        {result && (
          <div className="mt-3 space-y-2">
            <p
              role="status"
              className={cn(
                'rounded-lg p-2.5 text-sm font-medium',
                result.invalid > 0
                  ? 'bg-warning-soft text-warning'
                  : 'bg-success-soft text-success',
              )}
            >
              {result.message}
            </p>
            <div className="max-h-56 overflow-y-auto rounded-lg border border-border">
              <table className="w-full text-xs">
                <thead className="bg-muted/60 text-left">
                  <tr>
                    <th className="px-2 py-1">Line</th>
                    <th className="px-2 py-1">Name</th>
                    <th className="px-2 py-1">Result</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {result.rows.map((row) => (
                    <tr key={row.line}>
                      <td className="px-2 py-1 tabular-nums">{row.line}</td>
                      <td className="px-2 py-1">{row.name || '—'}</td>
                      <td
                        className={cn(
                          'px-2 py-1',
                          row.status === 'error' ? 'font-semibold text-warning' : 'text-success',
                        )}
                      >
                        {row.status === 'error'
                          ? (row.errors ?? []).join('; ')
                          : result.committed
                            ? 'Saved'
                            : 'Looks good'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
