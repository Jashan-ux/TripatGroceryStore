import type { ErrorResponse } from '@tripat/api-client';

import { env } from './env';

/** Shape thrown by every failed API call — mirrors the backend's single error shape. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;
  readonly requestId: string | null;

  constructor(
    status: number,
    code: string,
    message: string,
    details: Record<string, unknown> = {},
    requestId: string | null = null,
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }

  get isOffline(): boolean {
    return this.status === 0;
  }

  get isUnauthenticated(): boolean {
    return this.status === 401;
  }

  /** Field-level messages from a 422, keyed by field path. */
  get fieldErrors(): Record<string, string> {
    const fields = this.details.fields;
    if (!Array.isArray(fields)) return {};
    const out: Record<string, string> = {};
    for (const entry of fields) {
      if (entry && typeof entry === 'object' && 'field' in entry && 'message' in entry) {
        const field = String((entry as { field: unknown }).field);
        out[field] = String((entry as { message: unknown }).message);
      }
    }
    return out;
  }
}

export type AccessTokenProvider = () => Promise<string | null> | string | null;

let tokenProvider: AccessTokenProvider = () => null;

/**
 * Register how to obtain the Supabase access token. Auth lands in Phase 1; until
 * then no Authorization header is sent. Keeping this a single seam means no
 * component ever handles tokens directly.
 */
export function setAccessTokenProvider(provider: AccessTokenProvider): void {
  tokenProvider = provider;
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  body?: unknown;
  signal?: AbortSignal;
  headers?: Record<string, string>;
  /** Required for order placement and any credited action. */
  idempotencyKey?: string;
  timeoutMs?: number;
}

const DEFAULT_TIMEOUT_MS = 15_000;

function buildUrl(path: string): string {
  const base = env.apiBaseUrl;
  const normalised = path.startsWith('/') ? path : `/${path}`;
  return `${base}${normalised}`;
}

function parseError(status: number, payload: unknown): ApiError {
  const maybe = payload as Partial<ErrorResponse> | null;
  const error = maybe && typeof maybe === 'object' ? maybe.error : undefined;
  if (error && typeof error === 'object') {
    return new ApiError(
      status,
      error.code ?? 'error',
      error.message ?? 'Something went wrong.',
      error.details ?? {},
      error.request_id ?? null,
    );
  }
  return new ApiError(status, 'error', 'Something went wrong. Please try again.');
}

/** Core typed fetch. Never throws a non-ApiError. */
export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal, headers = {}, idempotencyKey, timeoutMs } = options;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs ?? DEFAULT_TIMEOUT_MS);
  const onAbort = () => controller.abort();
  signal?.addEventListener('abort', onAbort, { once: true });

  const token = await tokenProvider();
  const finalHeaders: Record<string, string> = { Accept: 'application/json', ...headers };
  if (body !== undefined) finalHeaders['Content-Type'] = 'application/json';
  if (token) finalHeaders.Authorization = `Bearer ${token}`;
  if (idempotencyKey) finalHeaders['Idempotency-Key'] = idempotencyKey;

  try {
    const response = await fetch(buildUrl(path), {
      method,
      headers: finalHeaders,
      body: body === undefined ? undefined : JSON.stringify(body),
      // Same-origin in production (rewrites); credentials only matter locally.
      credentials: 'same-origin',
      signal: controller.signal,
      cache: 'no-store',
    });

    if (response.status === 204) return undefined as T;

    const text = await response.text();
    const payload: unknown = text ? safeJson(text) : null;

    if (!response.ok) throw parseError(response.status, payload);
    return payload as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === 'AbortError') {
      const timedOut = !signal?.aborted;
      throw new ApiError(
        0,
        timedOut ? 'timeout' : 'aborted',
        timedOut ? 'The store took too long to respond. Please try again.' : 'Request cancelled.',
      );
    }
    throw new ApiError(
      0,
      'network_error',
      navigator.onLine
        ? 'We could not reach the store. Please try again.'
        : 'You are offline. Reconnect to place an order.',
    );
  } finally {
    clearTimeout(timeout);
    signal?.removeEventListener('abort', onAbort);
  }
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

/** Typed helpers used by feature modules. */
export const api = {
  get: <T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    apiFetch<T>(path, { ...options, method: 'GET' }),
  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    apiFetch<T>(path, { ...options, method: 'POST', body }),
  patch: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    apiFetch<T>(path, { ...options, method: 'PATCH', body }),
  put: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    apiFetch<T>(path, { ...options, method: 'PUT', body }),
  delete: <T>(path: string, options?: Omit<RequestOptions, 'method' | 'body'>) =>
    apiFetch<T>(path, { ...options, method: 'DELETE' }),
};
