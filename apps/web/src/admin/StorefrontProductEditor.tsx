import type { ProductAdminOut } from '@tripat/api-client';
import { useState, type FormEvent } from 'react';

import {
  useAdminBrands,
  useAdminCategories,
  useAdminProduct,
  useCreateProduct,
  useUpdateProduct,
  useUploadImage,
  type ProductDraft,
} from '@/admin/adminCatalogue';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Textarea } from '@/components/ui/textarea';
import { formatPaise } from '@/lib/utils';

interface VariantDraft {
  label: string;
  price: string;
  mrp: string;
  stock: number;
  isActive: boolean;
}

interface FormDraft {
  name: string;
  categoryId: string;
  brandId: string;
  description: string;
  unit: string;
  price: string;
  mrp: string;
  image: string;
  stock: string;
  isActive: boolean;
  isFeatured: boolean;
  variants: VariantDraft[];
}

function formFor(product?: ProductAdminOut): FormDraft {
  return {
    name: product?.name ?? '',
    categoryId: product?.category_id ?? '',
    brandId: product?.brand_id ?? '',
    description: product?.description ?? '',
    unit: product?.unit_label ?? '',
    price: product ? (product.price_paise / 100).toFixed(2) : '',
    mrp: product ? (product.mrp_paise / 100).toFixed(2) : '',
    image: product?.images?.[0] ?? '',
    stock: String(product?.stock ?? 0),
    isActive: product?.is_active ?? true,
    isFeatured: product?.is_featured ?? true,
    variants: (product?.variants ?? []).map((variant) => ({
      label: variant.label,
      price: (variant.price_paise / 100).toFixed(2),
      mrp: (variant.mrp_paise / 100).toFixed(2),
      stock: variant.stock,
      isActive: variant.is_active,
    })),
  };
}

function toPaise(value: string): number | null {
  if (!value.trim()) return null;
  const amount = Number(value);
  return Number.isFinite(amount) && amount >= 0 ? Math.round(amount * 100) : null;
}

export function StorefrontProductEditor({
  open,
  productId,
  onClose,
  onSaved,
}: {
  open: boolean;
  productId: string | null;
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const product = useAdminProduct(open && productId ? productId : null);
  const categories = useAdminCategories(open);
  const brands = useAdminBrands(open);
  const create = useCreateProduct();
  const update = useUpdateProduct();
  const upload = useUploadImage();
  const busy = create.isPending || update.isPending || upload.isPending;

  const initialProduct = productId ? product.data : undefined;
  const ready = !productId || product.isSuccess;
  const [draft, setDraft] = useState<FormDraft | null>(null);
  const [draftKey, setDraftKey] = useState<string | null>(null);
  const key = initialProduct?.id ?? (productId ? null : 'new');
  if (key && draftKey !== key) {
    setDraftKey(key);
    setDraft(formFor(initialProduct));
  }

  const close = () => {
    setDraft(null);
    setDraftKey(null);
    onClose();
  };

  const save = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!draft) return;
    const name = draft.name.trim();
    const variantLabels = draft.variants.map((variant) => variant.label.trim().toLocaleLowerCase());
    const variantsValid = draft.variants.every((variant) => {
      const variantPrice = toPaise(variant.price);
      const variantMrp = variant.mrp.trim() ? toPaise(variant.mrp) : variantPrice;
      return Boolean(
        variant.label.trim() &&
          variantPrice !== null &&
          variantMrp !== null &&
          !(variantMrp > 0 && variantPrice > variantMrp) &&
          Number.isInteger(variant.stock) &&
          variant.stock >= 0,
      );
    });
    if (!variantsValid || new Set(variantLabels).size !== variantLabels.length) return;
    const price = toPaise(draft.price);
    const mrp = draft.mrp.trim() ? toPaise(draft.mrp) : price;
    if (!name || !draft.categoryId || price === null || mrp === null) return;
    if (mrp > 0 && price > mrp) return;

    const body: ProductDraft = {
      name,
      category_id: draft.categoryId,
      brand_id: draft.brandId || null,
      description: draft.description.trim(),
      unit_label: draft.unit.trim(),
      price_paise: price,
      mrp_paise: mrp,
      images: draft.image.trim() ? [draft.image.trim()] : [],
      ...(productId ? {} : { stock: Math.max(0, Math.floor(Number(draft.stock) || 0)) }),
      is_active: draft.isActive,
      is_featured: draft.isFeatured,
      ...(draft.variants.length > 0 || (initialProduct?.variants ?? []).length > 0
        ? {
            variants: draft.variants.map((variant, index) => ({
              label: variant.label.trim(),
              price_paise: toPaise(variant.price) ?? 0,
              mrp_paise: toPaise(variant.mrp) ?? toPaise(variant.price) ?? 0,
              stock: Math.max(0, Math.floor(variant.stock)),
              sort_order: index,
              is_active: variant.isActive,
            })),
          }
        : {}),
    };
    const onSuccess = (saved: ProductAdminOut) => {
      onSaved(`${saved.name} ${productId ? 'updated' : 'added'} on your storefront.`);
      close();
    };
    if (productId) {
      update.mutate({ id: productId, ...body }, { onSuccess });
    } else {
      create.mutate(body, { onSuccess });
    }
  };

  const categoryOptions = categories.data?.categories ?? [];
  const message = create.error?.message ?? update.error?.message ?? upload.error?.message;
  const priceValue = draft ? toPaise(draft.price) : null;
  const mrpValue = draft?.mrp.trim() ? toPaise(draft.mrp) : priceValue;
  const variantLabels =
    draft?.variants.map((variant) => variant.label.trim().toLocaleLowerCase()) ?? [];
  const variantsValid = Boolean(
    draft &&
      draft.variants.every((variant) => {
        const variantPrice = toPaise(variant.price);
        const variantMrp = variant.mrp.trim() ? toPaise(variant.mrp) : variantPrice;
        return Boolean(
          variant.label.trim() &&
            variantPrice !== null &&
            variantMrp !== null &&
            !(variantMrp > 0 && variantPrice > variantMrp) &&
            Number.isInteger(variant.stock) &&
            variant.stock >= 0,
        );
      }) &&
      new Set(variantLabels).size === variantLabels.length,
  );
  const canSave = Boolean(
    draft?.name.trim() &&
      !categories.isPending &&
      !categories.isError &&
      draft.categoryId &&
      (productId || (Number.isInteger(Number(draft.stock)) && Number(draft.stock) >= 0)) &&
      priceValue !== null &&
      mrpValue !== null &&
      !(mrpValue > 0 && priceValue > mrpValue) &&
      variantsValid &&
      !busy,
  );

  return (
    <Dialog open={open} onOpenChange={(next) => !next && close()}>
      <DialogContent className="max-h-[92dvh] w-[min(96vw,38rem)] overflow-y-auto">
        <DialogTitle>{productId ? 'Edit this product' : 'Add a product'}</DialogTitle>
        <DialogDescription>
          Make changes here and they update the storefront customers see.
        </DialogDescription>
        {productId && product.isError ? (
          <div role="alert" className="mt-4 rounded-lg bg-warning-soft p-3 text-sm text-warning">
            Could not load this product: {product.error.message}
          </div>
        ) : !ready ? (
          <p role="status" className="mt-5 text-sm text-muted-foreground">
            Loading product details…
          </p>
        ) : !draft ? (
          <p role="status" className="mt-5 text-sm text-muted-foreground">
            Preparing the editor…
          </p>
        ) : (
          <form className="mt-4 space-y-3" onSubmit={save}>
            <label className="block text-sm font-semibold" htmlFor="store-editor-name">
              Product name
              <Input
                id="store-editor-name"
                className="mt-1"
                value={draft.name}
                onChange={(event) => setDraft({ ...draft, name: event.target.value })}
                required
                maxLength={200}
              />
            </label>
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="block text-sm font-semibold" htmlFor="store-editor-category">
                Category
                <Select
                  id="store-editor-category"
                  className="mt-1"
                  value={draft.categoryId}
                  onChange={(event) => setDraft({ ...draft, categoryId: event.target.value })}
                  required
                >
                  <option value="">Choose a category</option>
                  {categoryOptions.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.parent_name ? `${category.parent_name} › ` : ''}
                      {category.name}
                    </option>
                  ))}
                </Select>
                {categories.isError && (
                  <span className="mt-1 block text-xs font-normal text-warning" role="alert">
                    Categories did not load.{' '}
                    <button
                      type="button"
                      className="font-semibold underline"
                      onClick={() => void categories.refetch()}
                    >
                      Try again
                    </button>
                  </span>
                )}
              </label>
              <label className="block text-sm font-semibold" htmlFor="store-editor-brand">
                Brand (optional)
                <Select
                  id="store-editor-brand"
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
                {brands.isError && (
                  <span className="mt-1 block text-xs font-normal text-warning" role="alert">
                    Brands did not load.{' '}
                    <button
                      type="button"
                      className="font-semibold underline"
                      onClick={() => void brands.refetch()}
                    >
                      Try again
                    </button>
                  </span>
                )}
              </label>
            </div>
            <label className="block text-sm font-semibold" htmlFor="store-editor-description">
              Short description
              <Textarea
                id="store-editor-description"
                className="mt-1"
                rows={2}
                maxLength={4000}
                value={draft.description}
                onChange={(event) => setDraft({ ...draft, description: event.target.value })}
              />
            </label>
            <div className="grid gap-3 sm:grid-cols-3">
              <label className="block text-sm font-semibold" htmlFor="store-editor-price">
                Selling price (₹)
                <Input
                  id="store-editor-price"
                  className="mt-1"
                  type="number"
                  inputMode="decimal"
                  min="0"
                  step="0.01"
                  value={draft.price}
                  onChange={(event) => setDraft({ ...draft, price: event.target.value })}
                  required
                />
              </label>
              <label className="block text-sm font-semibold" htmlFor="store-editor-mrp">
                MRP (₹)
                <Input
                  id="store-editor-mrp"
                  className="mt-1"
                  type="number"
                  inputMode="decimal"
                  min="0"
                  step="0.01"
                  value={draft.mrp}
                  onChange={(event) => setDraft({ ...draft, mrp: event.target.value })}
                />
              </label>
              <label className="block text-sm font-semibold" htmlFor="store-editor-unit">
                Sold as
                <Input
                  id="store-editor-unit"
                  className="mt-1"
                  placeholder="1 kg, 500 ml…"
                  value={draft.unit}
                  onChange={(event) => setDraft({ ...draft, unit: event.target.value })}
                />
              </label>
            </div>
            <section
              className="space-y-3 rounded-xl border border-border p-3"
              aria-labelledby="store-editor-variants-title"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 id="store-editor-variants-title" className="text-sm font-semibold">
                    Pack options
                  </h3>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Add sizes or pack choices such as 500 g and 1 kg, each with its own price and
                    stock.
                  </p>
                </div>
                <Button
                  type="button"
                  variant="outline"
                  onClick={() =>
                    setDraft({
                      ...draft,
                      variants: [
                        ...draft.variants,
                        {
                          label: '',
                          price: draft.price,
                          mrp: draft.mrp || draft.price,
                          stock: 0,
                          isActive: true,
                        },
                      ],
                    })
                  }
                >
                  + Add pack
                </Button>
              </div>
              {draft.variants.map((variant, index) => (
                <fieldset key={`pack-${index}`} className="space-y-2 rounded-lg bg-muted/40 p-3">
                  <legend className="px-1 text-xs font-semibold text-muted-foreground">
                    Pack {index + 1}
                  </legend>
                  <div className="grid gap-2 sm:grid-cols-2">
                    <label
                      className="text-xs font-semibold"
                      htmlFor={`store-editor-variant-label-${index}`}
                    >
                      Pack name (for example, 1 kg)
                      <Input
                        id={`store-editor-variant-label-${index}`}
                        className="mt-1"
                        value={variant.label}
                        onChange={(event) =>
                          setDraft({
                            ...draft,
                            variants: draft.variants.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, label: event.target.value } : item,
                            ),
                          })
                        }
                        required
                        maxLength={100}
                      />
                    </label>
                    <label
                      className="text-xs font-semibold"
                      htmlFor={`store-editor-variant-stock-${index}`}
                    >
                      Stock available
                      <Input
                        id={`store-editor-variant-stock-${index}`}
                        className="mt-1"
                        type="number"
                        min="0"
                        step="1"
                        value={variant.stock}
                        onChange={(event) =>
                          setDraft({
                            ...draft,
                            variants: draft.variants.map((item, itemIndex) =>
                              itemIndex === index
                                ? {
                                    ...item,
                                    stock: Math.max(0, Math.floor(Number(event.target.value) || 0)),
                                  }
                                : item,
                            ),
                          })
                        }
                      />
                    </label>
                    <label
                      className="text-xs font-semibold"
                      htmlFor={`store-editor-variant-price-${index}`}
                    >
                      Selling price (₹)
                      <Input
                        id={`store-editor-variant-price-${index}`}
                        className="mt-1"
                        type="number"
                        min="0"
                        step="0.01"
                        value={variant.price}
                        onChange={(event) =>
                          setDraft({
                            ...draft,
                            variants: draft.variants.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, price: event.target.value } : item,
                            ),
                          })
                        }
                        required
                      />
                    </label>
                    <label
                      className="text-xs font-semibold"
                      htmlFor={`store-editor-variant-mrp-${index}`}
                    >
                      MRP (₹)
                      <Input
                        id={`store-editor-variant-mrp-${index}`}
                        className="mt-1"
                        type="number"
                        min="0"
                        step="0.01"
                        value={variant.mrp}
                        onChange={(event) =>
                          setDraft({
                            ...draft,
                            variants: draft.variants.map((item, itemIndex) =>
                              itemIndex === index ? { ...item, mrp: event.target.value } : item,
                            ),
                          })
                        }
                      />
                    </label>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <label className="flex min-h-touch items-center gap-2 text-xs font-medium">
                      <input
                        type="checkbox"
                        checked={variant.isActive}
                        onChange={(event) =>
                          setDraft({
                            ...draft,
                            variants: draft.variants.map((item, itemIndex) =>
                              itemIndex === index
                                ? { ...item, isActive: event.target.checked }
                                : item,
                            ),
                          })
                        }
                      />
                      Available to customers
                    </label>
                    <button
                      type="button"
                      className="min-h-touch px-2 text-xs font-semibold text-warning underline"
                      onClick={() =>
                        setDraft({
                          ...draft,
                          variants: draft.variants.filter((_, itemIndex) => itemIndex !== index),
                        })
                      }
                    >
                      Remove pack
                    </button>
                  </div>
                </fieldset>
              ))}
            </section>
            {!productId && draft.variants.length === 0 && (
              <label className="block max-w-48 text-sm font-semibold" htmlFor="store-editor-stock">
                Starting stock
                <Input
                  id="store-editor-stock"
                  className="mt-1"
                  type="number"
                  inputMode="numeric"
                  min="0"
                  step="1"
                  value={draft.stock}
                  onChange={(event) => setDraft({ ...draft, stock: event.target.value })}
                />
                <span className="mt-1 block text-xs font-normal text-muted-foreground">
                  Count what is available to sell.
                </span>
              </label>
            )}
            <label className="block text-sm font-semibold" htmlFor="store-editor-image">
              Product photo link
              <Input
                id="store-editor-image"
                className="mt-1"
                type="url"
                placeholder="Paste a photo link or upload a photo below"
                value={draft.image}
                onChange={(event) => setDraft({ ...draft, image: event.target.value })}
              />
            </label>
            <label className="block text-sm font-medium" htmlFor="store-editor-upload">
              Upload photo
              <Input
                id="store-editor-upload"
                className="mt-1"
                type="file"
                accept="image/jpeg,image/png,image/webp"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file)
                    upload.mutate(file, {
                      onSuccess: (image) =>
                        setDraft((current) =>
                          current ? { ...current, image: image.url } : current,
                        ),
                    });
                }}
              />
            </label>
            {draft.image && (
              <div className="flex items-center gap-3 rounded-lg border border-border p-2">
                <img
                  src={draft.image}
                  alt="Product preview"
                  className="size-14 rounded-md object-cover"
                />
                <p className="text-xs text-muted-foreground">Photo preview</p>
              </div>
            )}
            <div className="grid gap-2 rounded-xl bg-muted/50 p-3">
              <label className="flex min-h-touch items-center gap-2 text-sm font-semibold">
                <input
                  type="checkbox"
                  checked={draft.isActive}
                  onChange={(event) => setDraft({ ...draft, isActive: event.target.checked })}
                />
                Show product in the store
              </label>
              <label className="flex min-h-touch items-center gap-2 text-sm font-semibold">
                <input
                  type="checkbox"
                  checked={draft.isFeatured}
                  onChange={(event) => setDraft({ ...draft, isFeatured: event.target.checked })}
                />
                Show in the home page category shelf
              </label>
            </div>
            {productId && initialProduct && (
              <div className="rounded-lg border border-border px-3 py-2 text-xs text-muted-foreground">
                In stock: {initialProduct.available_stock}.{' '}
                {(initialProduct.variants ?? []).length > 0 ? (
                  'Edit pack-specific stock above. '
                ) : (
                  <>
                    To adjust stock safely, open{' '}
                    <a className="font-semibold text-primary underline" href="/admin/inventory">
                      Inventory
                    </a>
                    .
                  </>
                )}
              </div>
            )}
            {message && (
              <p role="alert" className="rounded-lg bg-warning-soft p-2.5 text-sm text-warning">
                {message}
              </p>
            )}
            {draft.price &&
              draft.mrp &&
              mrpValue !== null &&
              priceValue !== null &&
              mrpValue > 0 &&
              priceValue > mrpValue && (
                <p role="alert" className="text-sm text-warning">
                  Selling price cannot be higher than MRP.
                </p>
              )}
            <p className="text-xs text-muted-foreground">
              {productId && initialProduct
                ? `Current price: ${formatPaise(initialProduct.price_paise)}.`
                : 'Set a category and price to add this product.'}
            </p>
            <div className="flex gap-2 pt-1">
              <Button type="button" variant="outline" className="flex-1" onClick={close}>
                Cancel
              </Button>
              <Button type="submit" className="flex-1" disabled={!canSave}>
                {busy ? 'Saving…' : productId ? 'Save changes' : 'Add product'}
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
