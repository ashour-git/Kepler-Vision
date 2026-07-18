/** Typed fetch client for the Kepler API. */

import type { ApiError } from "./types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export class ApiClientError extends Error {
  readonly code: string;
  readonly status: number;
  readonly retryable: boolean;
  readonly requestId: string | null;
  readonly details: Record<string, unknown> | undefined;

  constructor(
    status: number,
    body: ApiError,
    requestId: string | null,
  ) {
    super(body.error.message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = body.error.code;
    this.retryable = body.error.retryable;
    this.requestId = body.error.request_id ?? requestId;
    this.details = body.error.details;
  }
}

export interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "PUT" | "DELETE";
  body?: unknown;
  /** Access token. The auth client passes it on each request. */
  accessToken?: string | null;
  /** Idempotency-Key for mutating requests. */
  idempotencyKey?: string;
  /** External AbortSignal. */
  signal?: AbortSignal;
  /** Skip the 401 → refresh dance (e.g. for the refresh call itself). */
  skipAuthRefresh?: boolean;
}

export interface AuthAwareHandlers {
  /** Called when a 401 is received and a refresh is in progress. */
  onUnauthorized?: () => Promise<boolean>;
}

class ApiClient {
  private authHandlers: AuthAwareHandlers = {};

  setAuthHandlers(handlers: AuthAwareHandlers): void {
    this.authHandlers = handlers;
  }

  get baseUrl(): string {
    return API_BASE_URL;
  }

  async request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
    const url = `${API_BASE_URL}${path}`;
    const headers: Record<string, string> = {
      Accept: "application/json",
    };
    if (opts.body !== undefined) {
      headers["Content-Type"] = "application/json";
    }
    if (opts.accessToken) {
      headers.Authorization = `Bearer ${opts.accessToken}`;
    }
    if (opts.idempotencyKey) {
      headers["Idempotency-Key"] = opts.idempotencyKey;
    }

    const init: RequestInit = {
      method: opts.method ?? "GET",
      headers,
      credentials: "include",
    };
    if (opts.body !== undefined) {
      init.body = JSON.stringify(opts.body);
    }
    if (opts.signal) {
      init.signal = opts.signal;
    }

    const response = await fetch(url, init);

    if (response.status === 204) {
      return undefined as T;
    }

    if (response.status === 401 && !opts.skipAuthRefresh && this.authHandlers.onUnauthorized) {
      const recovered = await this.authHandlers.onUnauthorized();
      if (recovered) {
        // Retry once with the (now refreshed) access token
        const newToken = await this.fetchAccessToken();
        return this.request<T>(path, { ...opts, accessToken: newToken ?? undefined, skipAuthRefresh: true });
      }
    }

    const text = await response.text();
    let body: unknown = null;
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = { error: { code: "bad_response", message: text, request_id: null, retryable: false } };
      }
    }
    if (!response.ok) {
      const errBody = (body as ApiError | null) ?? {
        error: {
          code: "unknown",
          message: response.statusText,
          request_id: null,
          retryable: false,
        },
      };
      throw new ApiClientError(response.status, errBody, response.headers.get("X-Request-Id"));
    }
    return body as T;
  }

  /** Returns the current access token via a callback registered by auth-client. */
  private async fetchAccessToken(): Promise<string | null> {
    if (typeof window === "undefined") return null;
    try {
      const raw = window.localStorage.getItem("kepler.session.v1");
      if (!raw) return null;
      const parsed = JSON.parse(raw) as { accessToken?: string };
      return parsed.accessToken ?? null;
    } catch {
      return null;
    }
  }
}

const api = new ApiClient();
export default api;
