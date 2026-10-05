"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { TokenPair, User } from "./types";

/**
 * Session tokens live in *tab-scoped* sessionStorage (not cookies) so an instructor and
 * three trainees can run side by side in four tabs of one browser during a demo.
 * Access tokens are short-lived (15 min) and refresh tokens rotate on every use.
 */
type AuthState = {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  hydrated: boolean;
  setSession: (pair: TokenPair) => void;
  setUser: (user: User) => void;
  clear: () => void;
  setHydrated: () => void;
};

const memoryStorage = () => {
  const data = new Map<string, string>();
  return {
    getItem: (k: string) => data.get(k) ?? null,
    setItem: (k: string, v: string) => void data.set(k, v),
    removeItem: (k: string) => void data.delete(k),
  };
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      hydrated: false,
      setSession: (pair) =>
        set({ user: pair.user, accessToken: pair.access_token, refreshToken: pair.refresh_token }),
      setUser: (user) => set({ user }),
      clear: () => set({ user: null, accessToken: null, refreshToken: null }),
      setHydrated: () => set({ hydrated: true }),
    }),
    {
      name: "fogroom-auth",
      storage: createJSONStorage(() =>
        typeof window === "undefined" ? memoryStorage() : window.sessionStorage,
      ),
      partialize: (s) => ({ user: s.user, accessToken: s.accessToken, refreshToken: s.refreshToken }),
      onRehydrateStorage: () => (state) => state?.setHydrated(),
    },
  ),
);

export function homeFor(role: string | undefined): string {
  if (role === "INSTRUCTOR" || role === "ADMIN") return "/dashboard";
  if (role === "TRAINEE") return "/exercise";
  return "/login";
}
