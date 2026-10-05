"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";
import type { TokenPair, User } from "@/lib/types";
import { qk } from "./rooms";

export type Persona = "instructor" | "alpha" | "bravo" | "charlie";

export async function login(email: string, password: string): Promise<TokenPair> {
  const pair = await api<TokenPair>("/auth/login", { body: { email, password }, auth: false });
  useAuthStore.getState().setSession(pair);
  return pair;
}

export async function demoLogin(persona: Persona): Promise<TokenPair> {
  const pair = await api<TokenPair>("/auth/demo-login", { body: { persona }, auth: false });
  useAuthStore.getState().setSession(pair);
  return pair;
}

export async function register(body: { email: string; password: string; display_name: string }): Promise<TokenPair> {
  const pair = await api<TokenPair>("/auth/register", { body, auth: false });
  useAuthStore.getState().setSession(pair);
  return pair;
}

export function useMe(enabled = true) {
  return useQuery({
    queryKey: qk.me,
    queryFn: async () => {
      const user = await api<User>("/auth/me");
      useAuthStore.getState().setUser(user);
      return user;
    },
    enabled,
    meta: { silent: true },
    staleTime: 60_000,
  });
}

export function useUpdateProfile() {
  return useMutation({
    mutationFn: (body: { display_name?: string }) => api<User>("/auth/me", { method: "PATCH", body }),
    onSuccess: (user) => useAuthStore.getState().setUser(user),
  });
}

export function useDemoConfig() {
  return useQuery({
    queryKey: ["demo-config"],
    queryFn: () => api<{ demo_mode: boolean; personas: string[] }>("/auth/demo-config", { auth: false }),
    staleTime: Infinity,
    meta: { silent: true },
  });
}
