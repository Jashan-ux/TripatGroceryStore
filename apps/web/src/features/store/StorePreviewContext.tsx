/* eslint-disable react-refresh/only-export-components -- context and hook belong together. */
import { createContext, useContext } from 'react';

const AdminStoreViewContext = createContext(false);

export const AdminStoreViewProvider = AdminStoreViewContext.Provider;

export function useAdminStoreView(): boolean {
  return useContext(AdminStoreViewContext);
}
