import { LayoutGrid, Plus, Upload, Warehouse } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';

import { StorefrontProductEditor } from '@/admin/StorefrontProductEditor';
import { Button } from '@/components/ui/button';

export function StorefrontAdminBar() {
  const [adding, setAdding] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  return (
    <>
      <section aria-label="Store management" className="border-b border-primary/20 bg-primary/5">
        <div className="container flex max-w-screen-2xl flex-wrap items-center gap-2 py-2">
          <span className="mr-auto text-xs font-bold uppercase tracking-wide text-primary">
            Admin store view
          </span>
          <Button size="sm" onClick={() => setAdding(true)}>
            <Plus aria-hidden="true" /> Add product
          </Button>
          <Button asChild variant="outline" size="sm">
            <Link to="/admin/products?bulk=1">
              <Upload aria-hidden="true" /> Bulk add
            </Link>
          </Button>
          <Button asChild variant="ghost" size="icon" className="sm:hidden" aria-label="Categories">
            <Link to="/admin/categories">
              <LayoutGrid aria-hidden="true" />
            </Link>
          </Button>
          <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
            <Link to="/admin/categories">
              <LayoutGrid aria-hidden="true" /> Categories
            </Link>
          </Button>
          <Button asChild variant="ghost" size="icon" className="sm:hidden" aria-label="Inventory">
            <Link to="/admin/inventory">
              <Warehouse aria-hidden="true" />
            </Link>
          </Button>
          <Button asChild variant="ghost" size="sm" className="hidden sm:inline-flex">
            <Link to="/admin/inventory">
              <Warehouse aria-hidden="true" /> Stock
            </Link>
          </Button>
        </div>
        {notice && (
          <div className="container max-w-screen-2xl pb-2">
            <p
              role="status"
              className="rounded-md bg-success-soft px-3 py-1.5 text-sm text-success"
            >
              {notice}
            </p>
          </div>
        )}
      </section>
      <StorefrontProductEditor
        open={adding}
        productId={null}
        onClose={() => setAdding(false)}
        onSaved={setNotice}
      />
    </>
  );
}
