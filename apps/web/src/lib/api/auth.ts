/** Typed auth API calls. */

import api from "./client";
import type {
  CreateApiKeyInput,
  CreateApiKeyResult,
  Member,
  Me,
  RefreshResult,
  SignInInput,
  SignInResult,
  SignUpInput,
  SignUpResult,
  Tokens,
  ApiKey,
} from "./types";

export const authApi = {
  signUp(input: SignUpInput): Promise<SignUpResult> {
    return api.request<SignUpResult>("/v1/auth/sign-up", {
      method: "POST",
      body: input,
    });
  },

  signIn(input: SignInInput): Promise<SignInResult> {
    return api.request<SignInResult>("/v1/auth/sign-in", {
      method: "POST",
      body: input,
    });
  },

  refresh(refreshToken: string): Promise<RefreshResult> {
    return api.request<RefreshResult>("/v1/auth/refresh", {
      method: "POST",
      body: { refresh_token: refreshToken },
      skipAuthRefresh: true,
    });
  },

  signOut(refreshToken: string, accessToken: string): Promise<void> {
    return api.request<void>("/v1/auth/sign-out", {
      method: "POST",
      body: { refresh_token: refreshToken },
      accessToken,
    });
  },
};

export const usersApi = {
  me(accessToken: string): Promise<Me> {
    return api.request<Me>("/v1/users/me", { accessToken });
  },

  changePassword(
    accessToken: string,
    input: { current_password: string; new_password: string },
  ): Promise<void> {
    return api.request<void>("/v1/users/me/change-password", {
      method: "POST",
      body: input,
      accessToken,
    });
  },
};

export const apiKeysApi = {
  list(accessToken: string): Promise<ApiKey[]> {
    return api.request<ApiKey[]>("/v1/users/me/api-keys", { accessToken });
  },

  create(accessToken: string, input: CreateApiKeyInput): Promise<CreateApiKeyResult> {
    return api.request<CreateApiKeyResult>("/v1/users/me/api-keys", {
      method: "POST",
      body: input,
      accessToken,
    });
  },

  revoke(accessToken: string, id: string): Promise<void> {
    return api.request<void>(`/v1/users/me/api-keys/${id}`, {
      method: "DELETE",
      accessToken,
    });
  },
};

export const workspacesApi = {
  listMembers(accessToken: string, tenantId: string): Promise<Member[]> {
    return api.request<Member[]>(`/v1/workspaces/${tenantId}/members`, { accessToken });
  },

  inviteMember(
    accessToken: string,
    tenantId: string,
    input: { email: string; role: string; full_name?: string },
  ): Promise<Member> {
    return api.request<Member>(`/v1/workspaces/${tenantId}/members`, {
      method: "POST",
      body: input,
      accessToken,
    });
  },

  changeRole(
    accessToken: string,
    tenantId: string,
    userId: string,
    role: string,
  ): Promise<void> {
    return api.request<void>(`/v1/workspaces/${tenantId}/members/${userId}`, {
      method: "PATCH",
      body: { role },
      accessToken,
    });
  },

  removeMember(accessToken: string, tenantId: string, userId: string): Promise<void> {
    return api.request<void>(`/v1/workspaces/${tenantId}/members/${userId}`, {
      method: "DELETE",
      accessToken,
    });
  },
};

export type { Tokens };
