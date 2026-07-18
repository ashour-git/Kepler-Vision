"""Auth endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request, Response, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from ...application.identity.commands import (
    RefreshCommand,
    RefreshResult,
    SignInCommand,
    SignInResult,
    SignOutCommand,
    SignUpCommand,
    SignUpResult,
    refresh_session,
    sign_in,
    sign_out,
)
from ...core.errors import EmailAlreadyExistsError
from ..rate_limit import login_rate_limit_headers
from ..deps import (
    CurrentUserIdDep,
    JWTServiceDep,
    RefreshTokenStoreDep,
    UnitOfWorkDep,
)

router = APIRouter(prefix="/auth", tags=["auth"])


# --- Schemas ---------------------------------------------------------------


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SignUpIn(_StrictModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=1024)
    full_name: Optional[str] = Field(default=None, max_length=200)
    tenant_name: Optional[str] = Field(default=None, max_length=200)
    tenant_slug: Optional[str] = Field(default=None, max_length=64)
    region: str = Field(default="us-central1", max_length=64)


class SignInIn(_StrictModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=1024)
    tenant_id: Optional[str] = None


class RefreshIn(_StrictModel):
    refresh_token: str = Field(min_length=10)


class SignOutIn(_StrictModel):
    refresh_token: str = Field(min_length=10)


class _TokensOut(BaseModel):
    token_type: str
    access_token: str
    access_expires_at: int
    refresh_token: str
    refresh_expires_at: int


class _UserOut(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    avatar_url: Optional[str]
    locale: str
    timezone: str
    mfa_enabled: bool
    status: str
    created_at: str


class _TenantOut(BaseModel):
    id: str
    name: str
    slug: str
    plan: str
    status: str
    region: str


class SignUpOut(BaseModel):
    user: _UserOut | None = None
    tenant: _TenantOut | None = None
    tokens: _TokensOut | None = None
    scopes: list[str] = Field(default_factory=list)
    # When the email already exists we return 200 with a "check your inbox"
    # hint to prevent email enumeration. `account_exists` is true in that case.
    account_exists: bool = False


class SignInOut(BaseModel):
    user: _UserOut
    tenant: _TenantOut
    role: str
    tokens: _TokensOut
    scopes: list[str]


class RefreshOut(BaseModel):
    user_id: str
    tenant_id: str
    role: str
    scopes: list[str]
    tokens: _TokensOut


# --- Helpers ---------------------------------------------------------------


def _client_ip(request: Request) -> Optional[str]:
    if request.client is None:
        return None
    return request.client.host


def _user_agent(value: Optional[str]) -> Optional[str]:
    if value and len(value) > 1024:
        return value[:1024]
    return value


# --- Endpoints -------------------------------------------------------------


@router.post(
    "/sign-up",
    response_model=SignUpOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create account and tenant",
)
async def sign_up_endpoint(
    payload: SignUpIn,
    request: Request,
    response: Response,
    uow: UnitOfWorkDep,
    jwt_service: JWTServiceDep,
    refresh_store: RefreshTokenStoreDep,
) -> SignUpOut:
    cmd = SignUpCommand(
        email=str(payload.email),
        password=payload.password,
        full_name=payload.full_name,
        tenant_name=payload.tenant_name,
        tenant_slug=payload.tenant_slug,
        region=payload.region,
    )
    try:
        result: SignUpResult = await sign_up(
            cmd,
            uow=uow,
            jwt_service=jwt_service,
            refresh_store=refresh_store,
            ip=_client_ip(request),
            user_agent=_user_agent(request.headers.get("user-agent")),
        )
    except EmailAlreadyExistsError:
        # P1.3: Email enumeration fix. We don't reveal whether the email
        # is registered. The response is the same shape as a successful
        # signup, but the body is empty and `account_exists` is true.
        # A "sign-in / forgot password" email should be sent in the
        # background (out of scope for this patch).
        for k, v in login_rate_limit_headers(remaining=1).items():
            response.headers[k] = v
        return SignUpOut(account_exists=True)
    for k, v in login_rate_limit_headers(remaining=1).items():
        response.headers[k] = v
    return SignUpOut(
        user=_UserOut(**result.user.to_dict()),
        tenant=_TenantOut(**result.tenant.to_dict()),
        tokens=_TokensOut(**result.tokens.to_dict()),
        scopes=result.scopes,
    )


@router.post("/sign-in", response_model=SignInOut, summary="Authenticate")
async def sign_in_endpoint(
    payload: SignInIn,
    request: Request,
    response: Response,
    uow: UnitOfWorkDep,
    jwt_service: JWTServiceDep,
    refresh_store: RefreshTokenStoreDep,
) -> SignInOut:
    # P1.3: Email enumeration fix.
    # The endpoint always succeeds in shape; the actual user is later
    # verified by the use case. The 401 response is returned via the
    # global error envelope and does not differ between "no such user"
    # and "wrong password" — both return `invalid_credentials`.
    cmd = SignInCommand(
        email=str(payload.email),
        password=payload.password,
        user_agent=_user_agent(request.headers.get("user-agent")),
        ip=_client_ip(request),
        tenant_id=payload.tenant_id,
    )
    result: SignInResult = await sign_in(
        cmd,
        uow=uow,
        jwt_service=jwt_service,
        refresh_store=refresh_store,
        ip=_client_ip(request),
        user_agent=_user_agent(request.headers.get("user-agent")),
    )
    for k, v in login_rate_limit_headers(remaining=1).items():
        response.headers[k] = v
    return SignInOut(
        user=_UserOut(**result.user.to_dict()),
        tenant=_TenantOut(**result.tenant.to_dict()),
        role=result.role,
        tokens=_TokensOut(**result.tokens.to_dict()),
        scopes=result.scopes,
    )


@router.post("/refresh", response_model=RefreshOut, summary="Rotate tokens")
async def refresh_endpoint(
    payload: RefreshIn,
    request: Request,
    uow: UnitOfWorkDep,
    jwt_service: JWTServiceDep,
    refresh_store: RefreshTokenStoreDep,
) -> RefreshOut:
    cmd = RefreshCommand(
        refresh_token=payload.refresh_token,
        user_agent=_user_agent(request.headers.get("user-agent")),
        ip=_client_ip(request),
    )
    result: RefreshResult = await refresh_session(
        cmd,
        uow=uow,
        jwt_service=jwt_service,
        refresh_store=refresh_store,
        ip=_client_ip(request),
        user_agent=_user_agent(request.headers.get("user-agent")),
    )
    return RefreshOut(
        user_id=result.user_id,
        tenant_id=result.tenant_id,
        role=result.role,
        scopes=result.scopes,
        tokens=_TokensOut(**result.tokens.to_dict()),
    )


@router.post(
    "/sign-out",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke session",
)
async def sign_out_endpoint(
    payload: SignOutIn,
    uow: UnitOfWorkDep,
    jwt_service: JWTServiceDep,
    refresh_store: RefreshTokenStoreDep,
    user_id: CurrentUserIdDep,
) -> None:
    cmd = SignOutCommand(refresh_token=payload.refresh_token, user_id=user_id)
    await sign_out(cmd, uow=uow, jwt_service=jwt_service, refresh_store=refresh_store)
    return None
