/**
 * Talking to the shop.
 *
 * The form posts even when nobody is signed in — the shop's number is on the
 * page, and a customer with a complaint should not be asked to create an account
 * first. Signed-in customers get their name, phone and email filled in by the
 * server, so the form stays short.
 */
import type { FeedbackIn, FeedbackOut } from '@tripat/api-client';
import { useMutation } from '@tanstack/react-query';

import { api } from '@/lib/api';

export function useSendFeedback() {
  return useMutation<FeedbackOut, Error, FeedbackIn>({
    mutationFn: (body) => api.post<FeedbackOut>('/api/v1/feedback', body),
  });
}
