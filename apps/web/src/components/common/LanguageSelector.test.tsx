import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';

import { LanguageSelector } from '@/components/common/LanguageSelector';
import { OrderStatusBadge } from '@/components/orders/OrderStatusBadge';
import { getCurrentLanguage, persistLanguagePreference } from '@/i18n';

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

describe('LanguageSelector', () => {
  it('persists a language preference for the next page load', () => {
    persistLanguagePreference('hi');

    expect(window.localStorage.getItem('msg-store-language')).toBe('hi');
    expect(getCurrentLanguage()).toBe('hi');
  });

  it('renders the saved language with a translated accessible label', () => {
    persistLanguagePreference('hi');

    render(<LanguageSelector />);

    expect(screen.getByRole('combobox', { name: 'भाषा' })).toHaveValue('hi');
    expect(screen.getByRole('option', { name: 'हिंदी' })).toBeVisible();
    expect(screen.getByRole('option', { name: 'EN' })).toBeVisible();
  });

  it('renders translated order status copy using the saved language', () => {
    persistLanguagePreference('hi');

    render(<OrderStatusBadge status="out_for_delivery" />);

    expect(screen.getByText('डिलीवरी के लिए निकला')).toBeVisible();
  });
});
