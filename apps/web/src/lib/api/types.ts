/** Shared API types — mirror the backend Pydantic schemas. */

export interface ApiErrorBody {
  code: string;
  message: string;
  request_id: string | null;
  retryable: boolean;
  details?: Record<string, unknown>;
}

export interface ApiError {
  error: ApiErrorBody;
}

export interface Tokens {
  token_type: string;
  access_token: string;
  access_expires_at: number;
  refresh_token: string;
  refresh_expires_at: number;
}

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  locale: string;
  timezone: string;
  mfa_enabled: boolean;
  status: string;
  created_at: string;
}

export interface Tenant {
  id: string;
  name: string;
  slug: string;
  plan: string;
  status: string;
  region: string;
}

export interface MembershipSummary {
  tenant_id: string;
  role: string;
  accepted_at: string | null;
  created_at: string;
}

export interface Me {
  user: User;
  memberships: MembershipSummary[];
  default_tenant: Tenant | null;
  default_role: string | null;
  scopes: string[];
}

export interface SignUpInput {
  email: string;
  password: string;
  full_name?: string;
  tenant_name?: string;
  tenant_slug?: string;
  region?: string;
}

export interface SignUpResult {
  user: User;
  tenant: Tenant;
  tokens: Tokens;
  scopes: string[];
}

export interface SignInInput {
  email: string;
  password: string;
  tenant_id?: string;
}

export interface SignInResult {
  user: User;
  tenant: Tenant;
  role: string;
  tokens: Tokens;
  scopes: string[];
}

export interface RefreshResult {
  user_id: string;
  tenant_id: string;
  role: string;
  scopes: string[];
  tokens: Tokens;
}

export interface ApiKey {
  id: string;
  name: string;
  key_prefix: string;
  scopes: string[];
  status: string;
  last_used_at: string | null;
  expires_at: string | null;
  created_at: string;
}

export interface CreateApiKeyInput {
  name: string;
  scopes?: string[];
  expires_at?: string;
}

export interface CreateApiKeyResult {
  api_key: ApiKey;
  plaintext: string;
}

export interface Member {
  user_id: string;
  email: string;
  full_name: string | null;
  role: string;
  joined_at: string;
  accepted_at: string | null;
  status: string;
}
