/**
 * Admin catalogue, offers, settings and feedback — the data layer.
 *
 * Every mutation invalidates the queries whose answer it changed, including the
 * public storefront ones (`products`, `categories`). The owner should never have
 * to reload the shop to see their own edit.
 */
import type {
  AdminCategoryListOut,
  AdminProductListOut,
  BrandAdminOut,
  BrandListOut,
  BulkResultOut,
  CategoryAdminOut,
  CurrentOfferOut,
  FeedbackListOut,
  FeedbackOut,
  ImageOut,
  OfferIn,
  OfferListOut,
  OfferOut,
  ProductAdminOut,
  SettingsOut,
  SettingsPatchIn,
  AuditListOut,
} from '@tripat/api-client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { api, apiUpload } from '@/lib/api';

export const ADMIN_PAGE_SIZE = 20;

function bustCatalogue(queryClient: ReturnType<typeof useQueryClient>) {
  void queryClient.invalidateQueries({ queryKey: ['admin', 'catalogue'] });
  void queryClient.invalidateQueries({ queryKey: ['products'] });
  void queryClient.invalidateQueries({ queryKey: ['categories'] });
  void queryClient.invalidateQueries({ queryKey: ['home'] });
  void queryClient.invalidateQueries({ queryKey: ['admin', 'analytics', 'low-stock'] });
  void queryClient.invalidateQueries({ queryKey: ['admin', 'analytics', 'summary'] });
}

// --------------------------------------------------------------------------- //
// Products
// --------------------------------------------------------------------------- //
export interface ProductFilters {
  q: string;
  categoryId: string;
  lowStock: boolean;
  page: number;
}

export function useAdminProduct(productId: string | null) {
  return useQuery<ProductAdminOut>({
    queryKey: ['admin', 'catalogue', 'product', productId],
    queryFn: ({ signal }) =>
      api.get<ProductAdminOut>(`/api/v1/admin/catalogue/products/${productId}`, { signal }),
    enabled: Boolean(productId),
  });
}

export function useAdminProducts(filters: ProductFilters) {
  const params = new URLSearchParams({
    page: String(filters.page),
    page_size: String(ADMIN_PAGE_SIZE),
  });
  if (filters.q.trim()) params.set('q', filters.q.trim());
  if (filters.categoryId) params.set('category_id', filters.categoryId);
  if (filters.lowStock) params.set('low_stock', 'true');

  return useQuery<AdminProductListOut>({
    queryKey: ['admin', 'catalogue', 'products', params.toString()],
    queryFn: ({ signal }) =>
      api.get<AdminProductListOut>(`/api/v1/admin/catalogue/products?${params.toString()}`, {
        signal,
      }),
    staleTime: 15 * 1000,
  });
}

export interface ProductDraft {
  name: string;
  category_id: string;
  brand_id?: string | null;
  description?: string;
  unit_label?: string;
  mrp_paise?: number;
  price_paise: number;
  stock?: number;
  low_stock_threshold?: number;
  images?: string[];
  tags?: string[];
  is_active?: boolean;
}

export function useCreateProduct() {
  const queryClient = useQueryClient();
  return useMutation<ProductAdminOut, Error, ProductDraft>({
    mutationFn: (body) => api.post<ProductAdminOut>('/api/v1/admin/catalogue/products', body),
    onSuccess: () => bustCatalogue(queryClient),
  });
}

export function useUpdateProduct() {
  const queryClient = useQueryClient();
  return useMutation<ProductAdminOut, Error, { id: string } & Partial<ProductDraft>>({
    mutationFn: ({ id, ...body }) =>
      api.patch<ProductAdminOut>(`/api/v1/admin/catalogue/products/${id}`, body),
    onSuccess: () => bustCatalogue(queryClient),
  });
}

export function useDeleteProduct() {
  const queryClient = useQueryClient();
  return useMutation<{ outcome: string; message: string }, Error, string>({
    mutationFn: (id) =>
      api.delete<{ outcome: string; message: string }>(`/api/v1/admin/catalogue/products/${id}`),
    onSuccess: () => bustCatalogue(queryClient),
  });
}

export function useBulkImport() {
  const queryClient = useQueryClient();
  return useMutation<BulkResultOut, Error, { csv: string; dry_run: boolean }>({
    mutationFn: (body) => api.post<BulkResultOut>('/api/v1/admin/catalogue/products/bulk', body),
    onSuccess: (result) => {
      if (result.committed) bustCatalogue(queryClient);
    },
  });
}

export function useUploadImage() {
  return useMutation<ImageOut, Error, File>({
    mutationFn: (file) => {
      const form = new FormData();
      form.append('file', file);
      return apiUpload<ImageOut>('/api/v1/admin/catalogue/images', form);
    },
  });
}

// --------------------------------------------------------------------------- //
// Categories & brands
// --------------------------------------------------------------------------- //
export function useAdminCategories() {
  return useQuery<AdminCategoryListOut>({
    queryKey: ['admin', 'catalogue', 'categories'],
    queryFn: ({ signal }) =>
      api.get<AdminCategoryListOut>('/api/v1/admin/catalogue/categories', { signal }),
    staleTime: 30 * 1000,
  });
}

export function useCreateCategory() {
  const queryClient = useQueryClient();
  return useMutation<
    CategoryAdminOut,
    Error,
    { name: string; parent_id?: string | null; emoji?: string }
  >({
    mutationFn: (body) => api.post<CategoryAdminOut>('/api/v1/admin/catalogue/categories', body),
    onSuccess: () => bustCatalogue(queryClient),
  });
}

export function useUpdateCategory() {
  const queryClient = useQueryClient();
  return useMutation<
    CategoryAdminOut,
    Error,
    { id: string; name?: string; emoji?: string; parent_id?: string | null; is_active?: boolean }
  >({
    mutationFn: ({ id, ...body }) =>
      api.patch<CategoryAdminOut>(`/api/v1/admin/catalogue/categories/${id}`, body),
    onSuccess: () => bustCatalogue(queryClient),
  });
}

export function useDeleteCategory() {
  const queryClient = useQueryClient();
  return useMutation<
    { outcome: string; products_moved: number; children_moved: number; message: string },
    Error,
    { id: string; reassignTo?: string }
  >({
    mutationFn: ({ id, reassignTo }) => {
      const suffix = reassignTo ? `?reassign_to=${encodeURIComponent(reassignTo)}` : '';
      return api.delete(`/api/v1/admin/catalogue/categories/${id}${suffix}`);
    },
    onSuccess: () => bustCatalogue(queryClient),
  });
}

export function useAdminBrands() {
  return useQuery<BrandListOut>({
    queryKey: ['admin', 'catalogue', 'brands'],
    queryFn: ({ signal }) => api.get<BrandListOut>('/api/v1/admin/catalogue/brands', { signal }),
    staleTime: 30 * 1000,
  });
}

export function useCreateBrand() {
  const queryClient = useQueryClient();
  return useMutation<BrandAdminOut, Error, { name: string }>({
    mutationFn: (body) => api.post<BrandAdminOut>('/api/v1/admin/catalogue/brands', body),
    onSuccess: () => bustCatalogue(queryClient),
  });
}

export function useDeleteBrand() {
  const queryClient = useQueryClient();
  return useMutation<{ outcome: string }, Error, string>({
    mutationFn: (id) => api.delete<{ outcome: string }>(`/api/v1/admin/catalogue/brands/${id}`),
    onSuccess: () => bustCatalogue(queryClient),
  });
}

// --------------------------------------------------------------------------- //
// Offers
// --------------------------------------------------------------------------- //
export function useAdminOffers(page: number) {
  return useQuery<OfferListOut>({
    queryKey: ['admin', 'offers', page],
    queryFn: ({ signal }) =>
      api.get<OfferListOut>(`/api/v1/admin/offers?page=${page}&page_size=20`, { signal }),
    staleTime: 20 * 1000,
  });
}

export function useSendOffer() {
  const queryClient = useQueryClient();
  return useMutation<OfferOut, Error, OfferIn>({
    mutationFn: (body) => api.post<OfferOut>('/api/v1/admin/offers', body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'offers'] });
      // The banner and every customer's bell changed.
      void queryClient.invalidateQueries({ queryKey: ['offers'] });
      void queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
}

export function useCurrentOfferAdmin() {
  return useQuery<CurrentOfferOut>({
    queryKey: ['offers', 'current'],
    queryFn: ({ signal }) => api.get<CurrentOfferOut>('/api/v1/offers/current', { signal }),
    staleTime: 60 * 1000,
  });
}

// --------------------------------------------------------------------------- //
// Settings
// --------------------------------------------------------------------------- //
export function useAdminSettings() {
  return useQuery<SettingsOut>({
    queryKey: ['admin', 'settings'],
    queryFn: ({ signal }) => api.get<SettingsOut>('/api/v1/admin/settings', { signal }),
    staleTime: 0,
  });
}

export function useUpdateSettings() {
  const queryClient = useQueryClient();
  return useMutation<SettingsOut, Error, SettingsPatchIn>({
    mutationFn: (body) => api.patch<SettingsOut>('/api/v1/admin/settings', body),
    onSuccess: (data) => {
      queryClient.setQueryData(['admin', 'settings'], data);
      // The storefront reads the same row: minimum order, delivery days, contact.
      void queryClient.invalidateQueries({ queryKey: ['config'] });
      void queryClient.invalidateQueries({ queryKey: ['admin', 'audit'] });
    },
  });
}

// --------------------------------------------------------------------------- //
// Feedback inbox
// --------------------------------------------------------------------------- //
export function useAdminFeedback(status: 'new' | 'read' | 'all', page: number) {
  const params = new URLSearchParams({ page: String(page), page_size: '25' });
  if (status !== 'all') params.set('status', status);
  return useQuery<FeedbackListOut>({
    queryKey: ['admin', 'feedback', status, page],
    queryFn: ({ signal }) =>
      api.get<FeedbackListOut>(`/api/v1/admin/feedback?${params.toString()}`, { signal }),
    staleTime: 15 * 1000,
  });
}

export function useMarkFeedbackRead() {
  const queryClient = useQueryClient();
  return useMutation<FeedbackOut, Error, string>({
    mutationFn: (id) => api.post<FeedbackOut>(`/api/v1/admin/feedback/${id}/read`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['admin', 'feedback'] });
      void queryClient.invalidateQueries({ queryKey: ['admin', 'audit'] });
    },
  });
}

// --------------------------------------------------------------------------- //
// Audit trail
// --------------------------------------------------------------------------- //
export function useAdminAudit(entity: string, page: number) {
  const params = new URLSearchParams({ page: String(page), page_size: '50' });
  if (entity) params.set('entity', entity);
  return useQuery<AuditListOut>({
    queryKey: ['admin', 'audit', entity, page],
    queryFn: ({ signal }) =>
      api.get<AuditListOut>(`/api/v1/admin/audit?${params.toString()}`, { signal }),
    staleTime: 10 * 1000,
  });
}
