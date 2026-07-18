/** Client-side auth session store and helpers. */

import api from "./client";
import { authApi, usersApi } from "./auth";
import type { Me, Tokens, User, Tenant } from "./types";

const STORAGE_KEY = "kepler.session.v1";
export const ACCESS_TOKEN_STORAGE_KEY = "kepler.access-token.v1";

export interface Session {
  accessToken: string;
  refreshToken: string;
  accessExpiresAt: number;
  refreshExpiresAt: number;
  user: User;
  tenant: Tenant | null;
  role: string | null;
  scopes: string[];
}

function isBrowser(): boolean {
  return typeof window !== "undefined";
}

export function readSession(): Session | null {
  if (!isBrowser()) return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Session;
    if (!parsed.accessToken || !parsed.refreshToken) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function writeSession(session: Session): void {
  if (!isBrowser()) return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    window.localStorage.setItem(ACCESS_TOKEN_STORAGE_KEY, session.accessToken);
  } catch {
    // ignore quota errors
  }
}

export function clearSession(): void {
  if (!isBrowser()) return;
  try {
    window.localStorage.removeItem(STORAGE_KEY);
    window.localStorage.removeItem(ACCESS_TOKEN_STORAGE_KEY);
  } catch {
    // ignore
  }
}

export function getAccessToken(): string | null {
  if (!isBrowser()) return null;
  try {
    return window.localStorage.getItem(ACCESS_TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function isAccessTokenExpired(session: Session, skewSeconds = 30): boolean {
  return session.accessExpiresAt * 1000 <= Date.now() + skewSeconds * 1000;
}

/** Schedule silent refresh of the access token. Returns a promise that
 * resolves with the new access token or null on failure. */
export async function refreshAccessToken(): Promise<string | null> {
  const session = readSession();
  if (!session) return null;
  try {
    const result = await authApi.refresh(session.refreshToken);
    const next: Session = {
      ...session,
      accessToken: result.tokens.access_token,
      refreshToken: result.tokens.refresh_token,
      accessExpiresAt: result.tokens.access_expires_at,
      refreshExpiresAt: result.tokens.refresh_expires_at,
    };
    writeSession(next);
    return next.accessToken;
  } catch {
    clearSession();
    return null;
  }
}

let inflightRefresh: Promise<string | null> | null = null;

export async function ensureFreshAccessToken(): Promise<string | null> {
  const session = readSession();
  if (!session) return null;
  if (!isAccessTokenExpired(session)) return session.accessToken;
  if (inflightRefresh) return inflightRefresh;
  inflightRefresh = refreshAccessToken().finally(() => {
    inflightRefresh = null;
  });
  return inflightRefresh;
}

export async function signInWithTokens(
  result: { tokens: Tokens; user: User; tenant: Tenant | null; role: string | null; scopes: string[] },
): Promise<Session> {
  const session: Session = {
    accessToken: result.tokens.access_token,
    refreshToken: result.tokens.refresh_token,
    accessExpiresAt: result.tokens.access_expires_at,
    refreshExpiresAt: result.tokens.refresh_expires_at,
    user: result.user,
    tenant: result.tenant,
    role: result.role,
    scopes: result.scopes,
  };
  writeSession(session);
  return session;
}

export async function fetchMe(accessToken: string): Promise<Me> {
  return usersApi.me(accessToken);
}

export async function signOutCurrent(): Promise<void> {
  const session = readSession();
  if (session) {
    try {
      await authApi.signOut(session.refreshToken, session.accessToken);
    } catch {
      // best effort
    }
  }
  clearSession();
}

api.setAuthHandlers({
  onUnauthorized: async () => {
    const next = await ensureFreshAccessToken();
    return next !== null;
  },
});
