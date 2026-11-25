/**
 * Catalogue queries.
 *
 * Every hook is keyed on exactly the parameters it sends, so changing a filter
 * creates a new cache entry instead of overwriting the previous page — that is
 * what makes "back" from a product feel instant.
 */
import type {
  BrandOut,
  CategoryTreeOut,
  HomeOut,
  ProductDetailOut,
  ProductListOut,
} from '@tripat/api-client';
import { keepPreviousData, useQuery } from '@tanstack/react-query';

import { api } from '@/lib/api';

export type SortKey = 'popular' | 'rating' | 'price_asc' | 'price_desc' | 'newest' | 'name';

export interface ProductQuery {
  q?: string;
  category?: string;
  brand?: string;
  minPricePaise?: number;
  maxPricePaise?: number;
  tags?: string[];
  inStockOnly?: boolean;
  sort?: SortKey;
  page?: number;
  pageSize?: number;
  /** Set false to keep a query idle (e.g. an empty search box). */
  enabled?: boolean;
}

export const PAGE_SIZE = 24;

function toSearchParams(query: ProductQuery): string {
  const params = new URLSearchParams();
  if (query.q?.trim()) params.set('q', query.q.trim());
  if (query.category) params.set('category', query.category);
  if (query.brand) params.set('brand', query.brand);
  if (query.minPricePaise !== undefined) params.set('min_price_paise', String(query.minPricePaise));
  if (query.maxPricePaise !== undefined) params.set('max_price_paise', String(query.maxPricePaise));
  if (query.tags?.length) params.set('tags', query.tags.join(','));
  if (query.inStockOnly) params.set('in_stock', 'true');
  params.set('sort', query.sort ?? 'popular');
  params.set('page', String(query.page ?? 1));
  params.set('page_size', String(query.pageSize ?? PAGE_SIZE));
  return params.toString();
}

export function productsQueryKey(query: ProductQuery) {
  return ['products', toSearchParams(query)] as const;
}

export function useCategories() {
  return useQuery<CategoryTreeOut[]>({
    queryKey: ['categories'],
    queryFn: ({ signal }) => api.get<CategoryTreeOut[]>('/api/v1/categories', { signal }),
    staleTime: 30 * 60 * 1000,
  });
}

export function useHome() {
  return useQuery<HomeOut>({
    queryKey: ['home'],
    queryFn: ({ signal }) => api.get<HomeOut>('/api/v1/home', { signal }),
    staleTime: 5 * 60 * 1000,
  });
}

export function useBrands() {
  return useQuery<BrandOut[]>({
    queryKey: ['brands'],
    queryFn: ({ signal }) => api.get<BrandOut[]>('/api/v1/brands', { signal }),
    staleTime: 30 * 60 * 1000,
  });
}

export function useProducts(query: ProductQuery) {
  return useQuery<ProductListOut>({
    queryKey: productsQueryKey(query),
    queryFn: ({ signal }) =>
      api.get<ProductListOut>(`/api/v1/products?${toSearchParams(query)}`, { signal }),
    placeholderData: keepPreviousData,
    staleTime: 60 * 1000,
    enabled: query.enabled ?? true,
  });
}

export function useProduct(slug: string | undefined) {
  return useQuery<ProductDetailOut>({
    queryKey: ['product', slug],
    queryFn: ({ signal }) =>
      api.get<ProductDetailOut>(`/api/v1/products/${encodeURIComponent(slug ?? '')}`, { signal }),
    enabled: Boolean(slug),
    staleTime: 5 * 60 * 1000,
  });
}

/** Human labels for the sort control (kept out of components so they stay translatable). */
export const SORT_OPTIONS: { value: SortKey; label: string }[] = [
  { value: 'popular', label: 'Popular' },
  { value: 'price_asc', label: 'Price: low to high' },
  { value: 'price_desc', label: 'Price: high to low' },
  { value: 'rating', label: 'Top rated' },
  { value: 'newest', label: 'Newest' },
  { value: 'name', label: 'Name (A–Z)' },
];
