import { describe, expect, it } from 'vitest';

import { decodeApplicationServerKey } from '@/features/notifications/push';

describe('web-push application server key', () => {
  it('decodes URL-safe, unpadded base64 into the subscription bytes', () => {
    expect([...decodeApplicationServerKey('AQID')]).toEqual([1, 2, 3]);
    expect([...decodeApplicationServerKey('-_8')]).toEqual([251, 255]);
  });
});
