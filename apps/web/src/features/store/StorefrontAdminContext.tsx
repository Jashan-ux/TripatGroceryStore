/* eslint-disable react-refresh/only-export-components -- context and hook belong together. */
import { createContext, useContext } from 'react';

export type StorefrontAdminContextValue = {
  editProduct: (productId: string) => void;
};

const StorefrontAdminContext = createContext<StorefrontAdminContextValue | null>(null);

export const StorefrontAdminProvider = StorefrontAdminContext.Provider;

export function useStorefrontAdmin(): StorefrontAdminContextValue | null {
  return useContext(StorefrontAdminContext);
}
