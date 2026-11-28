import { en, type Dictionary } from './en';
import { hi } from './hi';

export type Language = 'en' | 'hi';

const LANGUAGE_KEY = 'msg-store-language';
const dictionaries: Record<Language, Dictionary> = { en, hi };

export const DEFAULT_LANGUAGE: Language = 'en';

/** Read the saved choice without letting disabled storage break the storefront. */
export function getCurrentLanguage(): Language {
  if (typeof window === 'undefined') return DEFAULT_LANGUAGE;
  try {
    const saved = window.localStorage.getItem(LANGUAGE_KEY);
    if (saved === 'hi' || saved === 'en') return saved;
  } catch {
    // Storage can be unavailable in private browsing or locked-down webviews.
  }
  return DEFAULT_LANGUAGE;
}

/** Save the preference independently so persistence can be tested without navigation. */
export function persistLanguagePreference(language: Language): void {
  if (typeof window === 'undefined') return;
  try {
    window.localStorage.setItem(LANGUAGE_KEY, language);
  } catch {
    // Continue in the current language when storage is disabled.
  }
}

/** Persist the user's choice and reload so every route picks up translated copy. */
export function setCurrentLanguage(language: Language): void {
  if (typeof window === 'undefined') return;
  persistLanguagePreference(language);
  window.location.reload();
}

function lookup(dictionary: Dictionary, key: string): string | undefined {
  let node: unknown = dictionary;
  for (const segment of key.split('.')) {
    if (typeof node !== 'object' || node === null) return undefined;
    node = (node as Record<string, unknown>)[segment];
  }
  return typeof node === 'string' ? node : undefined;
}

/** Missing Hindi copy falls back to English rather than a missing-key placeholder. */
export function translate(language: Language, key: string): string {
  return lookup(dictionaries[language], key) ?? lookup(en, key) ?? key;
}

export const t = (key: string, language: Language = getCurrentLanguage()): string =>
  translate(language, key);

export type { Dictionary };
