/* eslint-disable react-refresh/only-export-components -- context and hook belong together. */
import { createContext, useContext } from 'react';

const StorePreviewContext = createContext(false);

export const StorePreviewProvider = StorePreviewContext.Provider;

export function useStorePreview(): boolean {
  return useContext(StorePreviewContext);
}
