import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { ProductThumb } from '@/components/catalogue/ProductCard';

describe('ProductThumb', () => {
  it('falls back to the standard product monogram when a remote image fails', () => {
    render(<ProductThumb name="MSG Premium Mustard Oil" imageUrl="https://shop.msgalltrading.com/oil.jpg" />);

    fireEvent.error(screen.getByRole('img', { name: 'MSG Premium Mustard Oil' }));

    expect(screen.queryByRole('img', { name: 'MSG Premium Mustard Oil' })).not.toBeInTheDocument();
    expect(screen.getByText('MP')).toBeInTheDocument();
  });

  it('uses a new image URL after a previous URL failed', () => {
    const { rerender } = render(<ProductThumb name="MSG Rice" imageUrl="https://example.com/old.jpg" />);
    fireEvent.error(screen.getByRole('img', { name: 'MSG Rice' }));

    rerender(<ProductThumb name="MSG Rice" imageUrl="https://example.com/new.jpg" />);

    expect(screen.getByRole('img', { name: 'MSG Rice' })).toHaveAttribute(
      'src',
      'https://example.com/new.jpg',
    );
  });
});
