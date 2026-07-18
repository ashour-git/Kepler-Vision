/** Client-side auth hooks backed by TanStack Query. */

"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { authApi, usersApi } from "../api/auth";
import {
  clearSession,
  fetchMe,
  getAccessToken,
  readSession,
  refreshAccessToken,
  signInWithTokens,
  signOutCurrent,
  writeSession,
  type Session,
} from "../api/auth-client";
import type { Me, SignInInput, SignUpInput } from "../api/types";

/** Query key factory. */
export const authKeys = {
  all: ["auth"] as const,
  me: () => [...authKeys.all, "me"] as const,
};

export function useSession(): Session | null {
  if (typeof window === "undefined") return null;
  return readSession();
}

export function useMe(enabled = true) {
  return useQuery<Me | null>({
    queryKey: authKeys.me(),
    enabled,
    queryFn: async () => {
      const token = getAccessToken();
      if (!token) return null;
      try {
        return await fetchMe(token);
      } catch {
        // Try a silent refresh once.
        const refreshed = await refreshAccessToken();
        if (!refreshed) return null;
        return await usersApi.me(refreshed);
      }
    },
    staleTime: 60 * 1000,
    refetchOnWindowFocus: true,
  });
}

export function useSignUp() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: SignUpInput) => {
      const result = await authApi.signUp(input);
      return result;
    },
    onSuccess: async (result) => {
      const session = await signInWithTokens({
        tokens: result.tokens,
        user: result.user,
        tenant: result.tenant,
        role: "owner",
        scopes: result.scopes,
      });
      writeSession(session);
      await qc.invalidateQueries({ queryKey: authKeys.all });
    },
  });
}

export function useSignIn() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (input: SignInInput) => {
      const result = await authApi.signIn(input);
      return result;
    },
    onSuccess: async (result) => {
      const session = await signInWithTokens({
        tokens: result.tokens,
        user: result.user,
        tenant: result.tenant,
        role: result.role,
        scopes: result.scopes,
      });
      writeSession(session);
      await qc.invalidateQueries({ queryKey: authKeys.all });
    },
  });
}

export function useSignOut() {
  const qc = useQueryClient();
  const router = useRouter();
  return useMutation({
    mutationFn: async () => {
      await signOutCurrent();
    },
    onSettled: () => {
      clearSession();
      qc.clear();
      router.replace("/sign-in");
    },
  });
}

/** Imperative hook to ensure the access token is fresh. */
export function useEnsureFreshAccessToken(): void {
  useEffect(() => {
    if (typeof window === "undefined") return;
    const session = readSession();
    if (!session) return;
    const skew = 60_000;
    if (session.accessExpiresAt * 1000 - Date.now() < skew) {
      void refreshAccessToken();
    }
  }, []);
}
