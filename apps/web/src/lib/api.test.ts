import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError, api, apiFetch, setAccessTokenProvider, setUnauthorizedHandler } from './api';

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

afterEach(() => {
  setAccessTokenProvider(() => null);
  setUnauthorizedHandler(null);
  vi.unstubAllGlobals();
});

describe('apiFetch', () => {
  it('parses a successful JSON response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => jsonResponse({ status: 'ok' })),
    );
    await expect(api.get<{ status: string }>('/api/v1/status')).resolves.toEqual({ status: 'ok' });
  });

  it('uses same-origin API paths when no API base override is configured', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL) => jsonResponse({ status: 'ok' }));
    vi.stubGlobal('fetch', fetchMock);
    await api.get('/api/v1/config');
    expect(fetchMock.mock.calls[0]?.[0]).toBe('/api/v1/config');
  });

  it('clears a stale session on 401 without retrying the request', async () => {
    const fetchMock = vi.fn(async () => jsonResponse({ error: { code: 'unauthorized' } }, 401));
    const onUnauthorized = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    setUnauthorizedHandler(onUnauthorized);

    await expect(api.post('/api/v1/orders', { items: [] })).rejects.toMatchObject({
      status: 401,
      code: 'unauthorized',
    });
    expect(onUnauthorized).toHaveBeenCalledOnce();
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it('maps the backend error shape to ApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () =>
        jsonResponse(
          {
            error: {
              code: 'validation_error',
              message: 'Some fields need fixing.',
              details: {
                fields: [
                  { field: 'phone', message: 'Enter a valid mobile number', type: 'value_error' },
                ],
              },
              request_id: 'req-1',
            },
          },
          422,
        ),
      ),
    );

    await expect(api.get('/api/v1/me')).rejects.toMatchObject({
      status: 422,
      code: 'validation_error',
      requestId: 'req-1',
    });

    try {
      await api.get('/api/v1/me');
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      expect((error as ApiError).fieldErrors).toEqual({
        phone: 'Enter a valid mobile number',
      });
    }
  });

  it('never caches and always sends no-store', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse({}),
    );
    vi.stubGlobal('fetch', fetchMock);
    await api.get('/api/v1/config');
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.cache).toBe('no-store');
  });

  it('sends the auth token and idempotency key when configured', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse({}),
    );
    vi.stubGlobal('fetch', fetchMock);
    setAccessTokenProvider(() => 'jwt-token');
    await api.post('/api/v1/orders', { items: [] }, { idempotencyKey: 'abc-123' });
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    const headers = init.headers as Record<string, string>;
    expect(headers.Authorization).toBe('Bearer jwt-token');
    expect(headers['Idempotency-Key']).toBe('abc-123');
    expect(headers['Content-Type']).toBe('application/json');
  });

  it('turns a network failure into an offline-friendly ApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch');
      }),
    );
    await expect(api.get('/api/v1/config')).rejects.toMatchObject({
      status: 0,
      code: 'network_error',
    });
  });

  it('sends a JSON body with DELETE requests when the endpoint requires it', async () => {
    const fetchMock = vi.fn(async (_input: RequestInfo | URL, _init?: RequestInit) =>
      jsonResponse({ enabled: false, message: 'off' }),
    );
    vi.stubGlobal('fetch', fetchMock);
    await api.delete('/api/v1/push/subscribe', {
      body: { endpoint: 'https://push.example.test/endpoint', keys: { p256dh: 'p', auth: 'a' } },
    });
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.method).toBe('DELETE');
    expect(JSON.parse(String(init.body))).toMatchObject({
      endpoint: 'https://push.example.test/endpoint',
    });
    expect((init.headers as Record<string, string>)['Content-Type']).toBe('application/json');
  });

  it('returns undefined for 204 responses', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(null, { status: 204 })),
    );
    await expect(
      apiFetch('/api/v1/notifications/1', { method: 'DELETE' }),
    ).resolves.toBeUndefined();
  });
});
