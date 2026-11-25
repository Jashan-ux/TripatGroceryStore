import type { CategoryAdminOut } from '@tripat/api-client';
import { Pencil, Plus, Trash2 } from 'lucide-react';
import { useState } from 'react';

import {
  useAdminCategories,
  useCreateCategory,
  useCreateProduct,
  useDeleteCategory,
  useUpdateCategory,
} from '@/admin/adminCatalogue';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Skeleton } from '@/components/ui/skeleton';
import { usePageTitle } from '@/hooks/usePageTitle';

interface InlineAdd {
  categoryId: string;
  name: string;
  price: string;
  unit: string;
}

const EMPTY_ADD: InlineAdd = { categoryId: '', name: '', price: '', unit: '1 kg' };

/**
 * Shelves, sub-shelves, and the fastest way to add a product to one.
 *
 * Every row carries its own "add product" row, because that is how the shop
 * actually works: a delivery arrives, the owner opens Categories, and types the
 * item straight onto the shelf it belongs to. Deleting is guarded by the server —
 * a shelf holding products is refused rather than silently emptied — and this
 * page offers the two honest choices: move them somewhere, or leave it alone.
 */
export function AdminCategoriesPage() {
  usePageTitle(undefined, 'Categories · Admin');
  const categories = useAdminCategories();
  const createCategory = useCreateCategory();
  const updateCategory = useUpdateCategory();
  const deleteCategory = useDeleteCategory();
  const createProduct = useCreateProduct();

  const [newName, setNewName] = useState('');
  const [newParent, setNewParent] = useState('');
  const [add, setAdd] = useState<InlineAdd>(EMPTY_ADD);
  const [editing, setEditing] = useState<CategoryAdminOut | null>(null);
  const [deleting, setDeleting] = useState<CategoryAdminOut | null>(null);
  const [reassignTo, setReassignTo] = useState('');
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const rows = categories.data?.categories ?? [];

  const createShelf = () => {
    setError(null);
    setNotice(null);
    createCategory.mutate(
      { name: newName.trim(), parent_id: newParent || null },
      {
        onSuccess: (category) => {
          setNotice(`“${category.name}” is live.`);
          setNewName('');
          setNewParent('');
        },
        onError: (err) => setError(err.message),
      },
    );
  };

  const addProduct = (category: CategoryAdminOut) => {
    setError(null);
    setNotice(null);
    const pricePaise = Math.round(Number(add.price.replace(/[^\d.]/g, '')) * 100);
    createProduct.mutate(
      {
        name: add.name.trim(),
        category_id: category.id,
        price_paise: pricePaise,
        mrp_paise: pricePaise,
        unit_label: add.unit.trim() || undefined,
      },
      {
        onSuccess: (product) => {
          setNotice(`${product.name} added to ${category.name}.`);
          setAdd({ ...EMPTY_ADD, categoryId: '' });
        },
        onError: (err) => setError(err.message),
      },
    );
  };

  const remove = (category: CategoryAdminOut) => {
    setError(null);
    setNotice(null);
    deleteCategory.mutate(
      { id: category.id, reassignTo: reassignTo || undefined },
      {
        onSuccess: (result) => {
          setNotice(result.message);
          setDeleting(null);
          setReassignTo('');
        },
        onError: (err) => setError(err.message),
      },
    );
  };

  return (
    <div className="container max-w-4xl space-y-4 py-5 pb-nav-safe md:pb-8">
      <h1 className="text-xl font-extrabold tracking-tight">Categories</h1>

      <section className="rounded-xl border border-border bg-card p-3">
        <h2 className="text-sm font-bold">New shelf</h2>
        <div className="mt-2 flex flex-wrap items-end gap-2">
          <label className="min-w-40 flex-1 text-xs font-semibold" htmlFor="name">
            Name
            <Input
              id="name"
              className="mt-1"
              value={newName}
              onChange={(event) => setNewName(event.target.value)}
              placeholder="Dry fruits"
            />
          </label>
          <label className="min-w-36 text-xs font-semibold" htmlFor="under">
            Under
            <Select
              id="under"
              className="mt-1"
              value={newParent}
              onChange={(event) => setNewParent(event.target.value)}
            >
              <option value="">Top level</option>
              {rows
                .filter((row) => !row.parent_id)
                .map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.name}
                  </option>
                ))}
            </Select>
          </label>
          <Button onClick={createShelf} disabled={createCategory.isPending || !newName.trim()}>
            <Plus aria-hidden="true" /> Add
          </Button>
        </div>
      </section>

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

      {categories.isPending ? (
        <Skeleton className="h-64 w-full rounded-xl" />
      ) : (
        <ul className="space-y-2">
          {rows.map((category) => (
            <li
              key={category.id}
              className="rounded-xl border border-border bg-card p-3"
              style={{ marginLeft: category.parent_id ? '1.25rem' : undefined }}
            >
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-semibold">
                  <span aria-hidden="true">{category.emoji ?? '🛒'}</span> {category.name}
                </p>
                <p className="text-xs text-muted-foreground">
                  {category.product_count} product{category.product_count === 1 ? '' : 's'}
                  {category.child_count > 0 ? ` · ${category.child_count} sub-shelf` : ''}
                  {category.is_active ? '' : ' · hidden'}
                </p>
                <div className="ml-auto flex gap-1">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() =>
                      setAdd(
                        add.categoryId === category.id
                          ? { ...EMPTY_ADD, categoryId: '' }
                          : { ...EMPTY_ADD, categoryId: category.id },
                      )
                    }
                  >
                    <Plus aria-hidden="true" /> Add product
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label={`Rename ${category.name}`}
                    onClick={() => setEditing(category)}
                  >
                    <Pencil aria-hidden="true" />
                  </Button>
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label={`Delete ${category.name}`}
                    onClick={() => {
                      setDeleting(category);
                      setReassignTo('');
                    }}
                  >
                    <Trash2 aria-hidden="true" />
                  </Button>
                </div>
              </div>

              {add.categoryId === category.id && (
                <div className="mt-2 grid gap-2 rounded-lg bg-muted/50 p-2 sm:grid-cols-4">
                  <label className="text-xs font-semibold sm:col-span-2" htmlFor="product-name">
                    Product name
                    <Input
                      id="product-name"
                      className="mt-1"
                      value={add.name}
                      onChange={(event) => setAdd({ ...add, name: event.target.value })}
                    />
                  </label>
                  <label className="text-xs font-semibold" htmlFor="price">
                    Price (₹)
                    <Input
                      id="price"
                      className="mt-1"
                      inputMode="decimal"
                      value={add.price}
                      onChange={(event) => setAdd({ ...add, price: event.target.value })}
                    />
                  </label>
                  <div className="flex items-end">
                    <Button
                      className="w-full"
                      disabled={createProduct.isPending || !add.name.trim() || !add.price}
                      onClick={() => addProduct(category)}
                    >
                      Save
                    </Button>
                  </div>
                </div>
              )}
            </li>
          ))}
        </ul>
      )}

      {editing && (
        <Dialog open onOpenChange={(open) => !open && setEditing(null)}>
          <DialogContent>
            <DialogTitle>Rename {editing.name}</DialogTitle>
            <RenameForm
              category={editing}
              saving={updateCategory.isPending}
              onSave={(body) =>
                updateCategory.mutate(
                  { id: editing.id, ...body },
                  {
                    onSuccess: (updated) => {
                      setNotice(`Saved as “${updated.name}”.`);
                      setEditing(null);
                    },
                    onError: (err) => setError(err.message),
                  },
                )
              }
            />
          </DialogContent>
        </Dialog>
      )}

      {deleting && (
        <Dialog open onOpenChange={(open) => !open && setDeleting(null)}>
          <DialogContent>
            <DialogTitle>Delete {deleting.name}?</DialogTitle>
            <DialogDescription>
              {deleting.product_count > 0 || deleting.child_count > 0
                ? 'This shelf still has products or sub-shelves. Choose where they should go, or cancel.'
                : 'Nothing is on this shelf, so it can be removed cleanly.'}
            </DialogDescription>
            {(deleting.product_count > 0 || deleting.child_count > 0) && (
              <label className="mt-3 block text-xs font-semibold" htmlFor="move-them-to">
                Move them to
                <Select
                  id="move-them-to"
                  className="mt-1"
                  value={reassignTo}
                  onChange={(event) => setReassignTo(event.target.value)}
                >
                  <option value="">Choose a shelf…</option>
                  {rows
                    .filter((row) => row.id !== deleting.id && !row.parent_id)
                    .map((row) => (
                      <option key={row.id} value={row.id}>
                        {row.name}
                      </option>
                    ))}
                </Select>
              </label>
            )}
            <div className="mt-3 flex gap-2">
              <Button
                variant="destructive"
                disabled={deleteCategory.isPending}
                onClick={() => remove(deleting)}
              >
                {deleteCategory.isPending ? 'Working…' : 'Delete'}
              </Button>
              <Button variant="outline" onClick={() => setDeleting(null)}>
                Cancel
              </Button>
            </div>
            {deleteCategory.isError && (
              <p role="alert" className="mt-2 text-xs font-semibold text-warning">
                {deleteCategory.error.message}
              </p>
            )}
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

function RenameForm({
  category,
  onSave,
  saving,
}: {
  category: CategoryAdminOut;
  onSave: (body: { name: string; emoji?: string }) => void;
  saving: boolean;
}) {
  const [name, setName] = useState(category.name);
  const [emoji, setEmoji] = useState(category.emoji ?? '');

  return (
    <form
      className="mt-3 space-y-2"
      onSubmit={(event) => {
        event.preventDefault();
        onSave({ name: name.trim(), emoji: emoji.trim() });
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
      <label className="block text-xs font-semibold" htmlFor="emoji-optional">
        Emoji (optional)
        <Input
          id="emoji-optional"
          className="mt-1"
          value={emoji}
          maxLength={16}
          onChange={(event) => setEmoji(event.target.value)}
        />
      </label>
      <Button type="submit" disabled={saving} className="w-full">
        {saving ? 'Saving…' : 'Save'}
      </Button>
    </form>
  );
}
