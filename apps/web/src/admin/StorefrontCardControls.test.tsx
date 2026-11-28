import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ProductCard } from '@/components/catalogue/ProductCard';
import { AdminStoreViewProvider } from '@/features/store/StorePreviewContext';
import { StorefrontAdminProvider } from '@/features/store/StorefrontAdminContext';
import { renderWithProviders } from '@/test/render';

const product = {
  id: '11111111-1111-1111-1111-111111111111',
  name: 'Fresh Ghee',
  slug: 'fresh-ghee',
  category_slug: 'dairy',
  category_name: 'Dairy',
  brand_name: 'MSG',
  unit_label: '1 L',
  mrp_paise: 65000,
  price_paise: 62000,
  discount_percent: 5,
  image_url: null,
  rating: 4.5,
  stock: 5,
  in_stock: true,
  tags: [],
  has_variants: false,
};

describe('storefront card admin controls', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () =>
          new Response(
            JSON.stringify({
              environment: 'test',
              store_name: 'Store',
              store_phone: '',
              store_address: '',
              store_maps_url: '',
              feedback_email: '',
              phone_otp_enabled: false,
              turnstile_enabled: false,
              supabase_url: '',
              supabase_anon_key: '',
              vapid_public_key: '',
            }),
            { status: 200, headers: { 'Content-Type': 'application/json' } },
          ),
      ),
    );
  });

  it('opens the editor from the exact product card customers see', async () => {
    const user = userEvent.setup();
    const editProduct = vi.fn();
    renderWithProviders(
      <AdminStoreViewProvider value>
        <StorefrontAdminProvider value={{ editProduct }}>
          <ProductCard product={product} />
        </StorefrontAdminProvider>
      </AdminStoreViewProvider>,
    );

    await user.click(screen.getByRole('button', { name: 'Edit Fresh Ghee' }));
    expect(editProduct).toHaveBeenCalledWith(product.id);
    expect(screen.getByRole('button', { name: 'Add to cart' })).toBeDisabled();
  });
});
