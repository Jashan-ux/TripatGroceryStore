import { en, type Dictionary } from './en';

export type Language = 'en' | 'hi';

const dictionaries: Record<Language, Dictionary> = { en } as Record<Language, Dictionary>;

export const DEFAULT_LANGUAGE: Language = 'en';

/**
 * Minimal, dependency-free translation helper. `hi` is added in the final
 * phase; until a dictionary exists we fall back to English rather than showing
 * a missing-key placeholder.
 */
export function translate(language: Language, key: string): string {
  const dictionary = dictionaries[language] ?? en;
  const segments = key.split('.');
  let node: unknown = dictionary;
  for (const segment of segments) {
    if (typeof node !== 'object' || node === null) return key;
    node = (node as Record<string, unknown>)[segment];
  }
  return typeof node === 'string' ? node : key;
}

export const t = (key: string, language: Language = DEFAULT_LANGUAGE): string =>
  translate(language, key);

export type { Dictionary };
