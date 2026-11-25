/**
 * Cart → checkout → orders data layer.
 *
 * Quotes are *server* calls on purpose: the basket only holds ids and
 * quantities, and every rupee shown on screen comes back from
 * `POST /api/v1/checkout/quote`. That keeps prices, stock and the minimum-order
 * rule in one place (the API) instead of re-implementing store rules in the UI.
 *
 * Quotes are modelled as queries keyed by the exact basket + pincode so that
 * two tabs, back-navigation and re-renders all reuse one answer, and a changed
 * basket simply becomes a new cache entry.
 */
import type {
  AddressIn,
  AddressOut,
  OrderCancelIn,
  OrderListOut,
  OrderOut,
  QuoteIn,
  QuoteOut,
} from '@tripat/api-client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { useAuth } from '@/features/auth/useAuth';
import { api } from '@/lib/api';

export interface QuoteItem {
  product_id: string;
  variant_id?: string | null;
  quantity: number;
}

export function quoteQueryKey(items: QuoteItem[], pincode?: string | null) {
  const normalised = items.map((item) => [item.product_id, item.variant_id ?? '', item.quantity]);
  return ['quote', normalised, pincode ?? ''] as const;
}

/** Basket price/stock/eligibility, straight from the store. */
export function useQuote(items: QuoteItem[], pincode?: string | null) {
  return useQuery<QuoteOut>({
    queryKey: quoteQueryKey(items, pincode),
    queryFn: ({ signal }) => {
      const body: QuoteIn = { items, pincode: pincode || null };
      return api.post<QuoteOut>('/api/v1/checkout/quote', body, { signal });
    },
    enabled: items.length > 0,
    // Stock moves; a quote older than a minute is not worth trusting.
    staleTime: 30 * 1000,
    retry: false,
  });
}

export function useAddresses() {
  const { status } = useAuth();
  return useQuery<AddressOut[]>({
    queryKey: ['addresses'],
    queryFn: ({ signal }) => api.get<AddressOut[]>('/api/v1/addresses', { signal }),
    enabled: status === 'authenticated',
    staleTime: 5 * 60 * 1000,
  });
}

export function useSaveAddress() {
  const queryClient = useQueryClient();
  return useMutation<AddressOut, Error, { id?: string } & AddressIn>({
    mutationFn: ({ id, ...body }) =>
      id
        ? api.put<AddressOut>(`/api/v1/addresses/${id}`, body)
        : api.post<AddressOut>('/api/v1/addresses', body),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['addresses'] }),
  });
}

export function useDeleteAddress() {
  const queryClient = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => api.delete<void>(`/api/v1/addresses/${id}`),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ['addresses'] }),
  });
}

export interface PlaceOrderInput {
  addressId: string;
  /** Generated once per checkout attempt so a double tap cannot order twice. */
  idempotencyKey: string;
  customerNote?: string;
  items: QuoteItem[];
}

export function usePlaceOrder() {
  const queryClient = useQueryClient();
  return useMutation<OrderOut, Error, PlaceOrderInput>({
    mutationFn: ({ addressId, idempotencyKey, customerNote, items }) =>
      api.post<OrderOut>(
        '/api/v1/orders',
        {
          address_id: addressId,
          customer_note: customerNote ?? '',
          items: items.map((item) => ({
            product_id: item.product_id,
            variant_id: item.variant_id ?? null,
            quantity: item.quantity,
          })),
        },
        { idempotencyKey },
      ),
    onSuccess: (order) => {
      queryClient.setQueryData(['order', order.id], order);
      void queryClient.invalidateQueries({ queryKey: ['orders'] });
      // Placing an order decrements stock: any cached quote is now stale.
      void queryClient.invalidateQueries({ queryKey: ['quote'] });
    },
  });
}

export const ORDERS_PAGE_SIZE = 10;

export function useOrders(page = 1) {
  const { status } = useAuth();
  return useQuery<OrderListOut>({
    queryKey: ['orders', page],
    queryFn: ({ signal }) =>
      api.get<OrderListOut>(`/api/v1/orders?page=${page}&page_size=${ORDERS_PAGE_SIZE}`, {
        signal,
      }),
    enabled: status === 'authenticated',
    staleTime: 60 * 1000,
  });
}

export function useOrder(orderId: string | undefined) {
  const { status } = useAuth();
  return useQuery<OrderOut>({
    queryKey: ['order', orderId],
    queryFn: ({ signal }) => api.get<OrderOut>(`/api/v1/orders/${orderId}`, { signal }),
    enabled: status === 'authenticated' && Boolean(orderId),
  });
}

export function useCancelOrder() {
  const queryClient = useQueryClient();
  return useMutation<OrderOut, Error, { orderId: string; reason?: string }>({
    mutationFn: ({ orderId, reason }) => {
      const body: OrderCancelIn = { reason: reason ?? '' };
      return api.post<OrderOut>(`/api/v1/orders/${orderId}/cancel`, body);
    },
    onSuccess: (order) => {
      queryClient.setQueryData(['order', order.id], order);
      void queryClient.invalidateQueries({ queryKey: ['orders'] });
    },
  });
}

/** A cart line's server identity, used by every quote/order call. */
export function toQuoteItems(
  lines: { productId: string; variantId: string | null; quantity: number }[],
): QuoteItem[] {
  return lines.map((line) => ({
    product_id: line.productId,
    variant_id: line.variantId,
    quantity: line.quantity,
  }));
}
