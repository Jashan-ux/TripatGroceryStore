/**
 * Rewards data: the wallet, the referral programme, scratch cards and returns.
 *
 * Everything here is scoped by the bearer token — the API never takes a profile id
 * — so there is nothing to get wrong on the client side beyond showing the right
 * empty states.
 */
import type {
  ReferralProgramOut,
  ReturnOut,
  RewardsSummaryOut,
  ScratchCardListOut,
  ScratchRevealOut,
  WalletOut,
} from '@tripat/api-client';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { useAuth } from '@/features/auth/useAuth';
import { api } from '@/lib/api';

const WALLET_PAGE_SIZE = 20;

export function useRewards() {
  const { status } = useAuth();
  return useQuery<RewardsSummaryOut>({
    queryKey: ['rewards'],
    queryFn: ({ signal }) => api.get<RewardsSummaryOut>('/api/v1/rewards', { signal }),
    enabled: status === 'authenticated',
    staleTime: 30 * 1000,
  });
}

export function useWallet(page = 1) {
  const { status } = useAuth();
  return useQuery<WalletOut>({
    queryKey: ['wallet', page],
    queryFn: ({ signal }) =>
      api.get<WalletOut>(`/api/v1/rewards/wallet?page=${page}&page_size=${WALLET_PAGE_SIZE}`, {
        signal,
      }),
    enabled: status === 'authenticated',
    staleTime: 30 * 1000,
  });
}

export function useScratchCards() {
  const { status } = useAuth();
  return useQuery<ScratchCardListOut>({
    queryKey: ['scratch-cards'],
    queryFn: ({ signal }) =>
      api.get<ScratchCardListOut>('/api/v1/rewards/scratch-cards', { signal }),
    enabled: status === 'authenticated',
    staleTime: 30 * 1000,
  });
}

export function useRevealCard() {
  const queryClient = useQueryClient();
  return useMutation<ScratchRevealOut, Error, string>({
    mutationFn: (cardId) =>
      api.post<ScratchRevealOut>(`/api/v1/rewards/scratch-cards/${cardId}/reveal`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['scratch-cards'] });
      void queryClient.invalidateQueries({ queryKey: ['rewards'] });
      void queryClient.invalidateQueries({ queryKey: ['wallet'] });
    },
  });
}

export function useJoinReferral() {
  const queryClient = useQueryClient();
  return useMutation<ReferralProgramOut, Error, string>({
    mutationFn: (code) => api.post<ReferralProgramOut>('/api/v1/rewards/referral', { code }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['rewards'] });
      void queryClient.invalidateQueries({ queryKey: ['quote'] });
    },
  });
}

export function useReturns() {
  const { status } = useAuth();
  return useQuery<{ returns: ReturnOut[] }>({
    queryKey: ['returns'],
    queryFn: ({ signal }) => api.get<{ returns: ReturnOut[] }>('/api/v1/returns', { signal }),
    enabled: status === 'authenticated',
    staleTime: 30 * 1000,
  });
}

export interface ReturnRequest {
  orderId: string;
  items: { order_item_id: string; quantity: number }[];
  reason: string;
}

export function useRequestReturn() {
  const queryClient = useQueryClient();
  return useMutation<ReturnOut, Error, ReturnRequest>({
    mutationFn: ({ orderId, items, reason }) =>
      api.post<ReturnOut>(`/api/v1/orders/${orderId}/return`, { items, reason }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['returns'] });
      void queryClient.invalidateQueries({ queryKey: ['notifications'] });
    },
  });
}
