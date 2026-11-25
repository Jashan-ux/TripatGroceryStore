import type { ProfileOut } from '@tripat/api-client';
import type { Session, User } from '@supabase/supabase-js';
import { createContext } from 'react';

import type { ApiError } from '@/lib/api';

export type AuthStatus = 'loading' | 'authenticated' | 'anonymous';

export interface AuthContextValue {
  status: AuthStatus;
  session: Session | null;
  user: User | null;
  profile: ProfileOut | null;
  isAdmin: boolean;
  /** False when this build has no Supabase project configured (catalogue still works). */
  authAvailable: boolean;
  needsPhone: boolean;
  error: ApiError | null;
  refreshProfile: () => Promise<void>;
  signInWithPassword: (email: string, password: string) => Promise<void>;
  signUpWithPassword: (
    email: string,
    password: string,
    name: string,
  ) => Promise<{ needsEmailConfirmation: boolean }>;
  signInWithGoogle: (next?: string) => Promise<void>;
  sendPasswordReset: (email: string) => Promise<void>;
  signOut: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export const PROFILE_QUERY_KEY = ['me'] as const;
