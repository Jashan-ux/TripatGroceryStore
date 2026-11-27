import { afterEach, describe, expect, it } from 'vitest';

import { en } from '@/i18n/en';
import { hi } from '@/i18n/hi';
import { getCurrentLanguage, translate } from '@/i18n';

function stringPaths(value: Record<string, unknown>, prefix = ''): string[] {
  return Object.entries(value).flatMap(([key, child]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return typeof child === 'string'
      ? [path]
      : stringPaths(child as Record<string, unknown>, path);
  });
}

describe('Hindi language support', () => {
  afterEach(() => window.localStorage.clear());

  it('has a Hindi translation for every shipped dictionary key', () => {
    expect(stringPaths(hi)).toEqual(stringPaths(en));
  });

  it('uses the stored language and falls back to English for missing copy', () => {
    expect(getCurrentLanguage()).toBe('en');
    window.localStorage.setItem('msg-store-language', 'hi');
    expect(getCurrentLanguage()).toBe('hi');
    expect(translate('hi', 'nav.home')).toBe('होम');
    expect(translate('hi', 'future.untranslated')).toBe('future.untranslated');
  });
});
