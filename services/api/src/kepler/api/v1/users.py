"""Users endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from ...application.identity.commands import (
    ChangePasswordCommand,
    change_password,
)
from ...application.identity.queries import GetMeQuery, get_me
from ..deps import ActorPermissionsDep, UnitOfWorkDep

router = APIRouter(prefix="/users", tags=["users"])


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


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


class _MembershipOut(BaseModel):
    tenant_id: str
    role: str
    accepted_at: Optional[str]
    created_at: str


class MeOut(BaseModel):
    user: _UserOut
    memberships: list[_MembershipOut]
    default_tenant: Optional[_TenantOut]
    default_role: Optional[str]
    scopes: list[str]


class ChangePasswordIn(_StrictModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=12, max_length=1024)


@router.get("/me", response_model=MeOut, summary="Current user")
async def get_me_endpoint(
    uow: UnitOfWorkDep,
    user_id: str,
) -> MeOut:
    """Return the current user, memberships, default tenant, and scopes.

    The user_id is injected by `CurrentUserIdDep`. We use it via the route
    signature to keep the type contract explicit.
    """
    from ..deps import CurrentUserIdDep  # local import for clarity

    raise NotImplementedError  # replaced below


# Authenticated routes use the dependency-injected user id.
from ..deps import CurrentUserIdDep  # noqa: E402


@router.get(
    "/me",
    response_model=MeOut,
    summary="Current user",
)
async def get_me_endpoint(
    uow: UnitOfWorkDep,
    user_id: CurrentUserIdDep,
) -> MeOut:
    result = await get_me(GetMeQuery(user_id=user_id), uow=uow)
    return MeOut(
        user=_UserOut(**result.user.to_dict()),
        memberships=[_MembershipOut(**m) for m in result.memberships],
        default_tenant=_TenantOut(**result.default_tenant.to_dict()) if result.default_tenant else None,
        default_role=result.default_role,
        scopes=result.scopes,
    )


@router.post(
    "/me/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change own password",
)
async def change_password_endpoint(
    payload: ChangePasswordIn,
    uow: UnitOfWorkDep,
    user_id: CurrentUserIdDep,
) -> None:
    cmd = ChangePasswordCommand(
        user_id=user_id,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    await change_password(cmd, uow=uow)
    return None
