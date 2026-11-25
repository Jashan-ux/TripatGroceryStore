import { useContext } from 'react';

import { AuthContext, type AuthContextValue } from './context';

/** Read the session/profile context. Throws outside `<AuthProvider>`. */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside <AuthProvider>');
  return context;
}
