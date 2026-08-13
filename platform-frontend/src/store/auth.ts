import { create } from "zustand";
import { persist } from "zustand/middleware";

import { setAuthToken } from "@/api/client";
import type { Role } from "@/api/auth";

interface AuthState {
  token: string | null;
  role: Role | null;
  businessId: string | null;
  login: (params: { token: string; role: Role; businessId: string | null }) => void;
  logout: () => void;
}

/**
 * Only the JWT, role, and businessId are persisted to localStorage — never a
 * password or any provider/model secret. setAuthToken() (src/api/client.ts)
 * is kept in sync on every transition: login, logout, and rehydration from
 * localStorage on startup, so a page refresh keeps API calls authenticated.
 */
export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      role: null,
      businessId: null,
      login: ({ token, role, businessId }) => {
        setAuthToken(token);
        set({ token, role, businessId });
      },
      logout: () => {
        setAuthToken(null);
        set({ token: null, role: null, businessId: null });
      },
    }),
    {
      name: "platform-auth",
      partialize: (state) => ({
        token: state.token,
        role: state.role,
        businessId: state.businessId,
      }),
      onRehydrateStorage: () => (state) => {
        setAuthToken(state?.token ?? null);
      },
    },
  ),
);
