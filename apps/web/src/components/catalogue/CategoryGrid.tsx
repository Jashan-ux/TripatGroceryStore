import type { CategoryTreeOut } from '@tripat/api-client';
import { Link } from 'react-router-dom';

/**
 * Category tiles. Emoji come from the database (per-category, editable by the
 * owner); there is no generic "shop" icon repeated ten times.
 */
export function CategoryGrid({ categories }: { categories: CategoryTreeOut[] }) {
  if (categories.length === 0) return null;
  return (
    <section aria-labelledby="categories-heading" className="container pt-6">
      <h2 id="categories-heading" className="mb-3 text-base font-bold tracking-tight sm:text-lg">
        Shop by category
      </h2>
      <ul className="grid grid-cols-3 gap-2.5 sm:grid-cols-4 lg:grid-cols-5">
        {categories.map((category) => (
          <li key={category.id}>
            <Link
              to={`/categories/${category.slug}`}
              className="flex h-full flex-col items-center justify-center gap-1.5 rounded-xl border border-border bg-card px-2 py-3 text-center shadow-elev1 transition-colors hover:border-primary-300 hover:bg-primary-50"
            >
              <span aria-hidden="true" className="text-2xl leading-none">
                {category.emoji ?? '🛒'}
              </span>
              <span className="text-[12px] font-medium leading-tight text-foreground">
                {category.name}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
