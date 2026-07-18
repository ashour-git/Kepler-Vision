"""Workspaces endpoints (members management)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, EmailStr, Field

from ...application.identity.commands import (
    ChangeMemberRoleCommand,
    InviteMemberCommand,
    RemoveMemberCommand,
    change_member_role,
    invite_member,
    remove_member,
)
from ...application.identity.queries import ListMembersQuery, list_members
from ...domain.identity import Permission
from ..deps import (
    ActorPermissionsDep,
    CurrentTenantIdDep,
    CurrentUserIdDep,
    UnitOfWorkDep,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class InviteIn(_StrictModel):
    email: EmailStr
    role: str = Field(pattern="^(owner|admin|member|analyst|viewer|billing_admin|service)$")
    full_name: Optional[str] = Field(default=None, max_length=200)


class ChangeRoleIn(_StrictModel):
    role: str = Field(pattern="^(owner|admin|member|analyst|viewer|billing_admin|service)$")


class MemberOut(BaseModel):
    user_id: str
    email: str
    full_name: Optional[str]
    role: str
    joined_at: str
    accepted_at: Optional[str]
    status: str


@router.get(
    "/{tenant_id}/members",
    response_model=list[MemberOut],
    summary="List members",
)
async def list_members_endpoint(
    tenant_id: str,
    uow: UnitOfWorkDep,
    actor_permissions: ActorPermissionsDep,
) -> list[MemberOut]:
    rows = await list_members(
        ListMembersQuery(tenant_id=tenant_id, actor_permissions=actor_permissions),
        uow=uow,
    )
    return [MemberOut(**row) for row in rows]


@router.post(
    "/{tenant_id}/members",
    response_model=MemberOut,
    status_code=status.HTTP_201_CREATED,
    summary="Invite member",
)
async def invite_member_endpoint(
    tenant_id: str,
    payload: InviteIn,
    uow: UnitOfWorkDep,
    actor_permissions: ActorPermissionsDep,
    actor_id: CurrentUserIdDep,
) -> MemberOut:
    cmd = InviteMemberCommand(
        tenant_id=tenant_id,
        email=str(payload.email),
        role=payload.role,
        invited_by=actor_id,
        full_name=payload.full_name,
    )
    await invite_member(cmd, uow=uow, actor_permissions=actor_permissions)
    # Return the new member
    from ...application.identity.queries import list_members as _list_members
    from ...application.identity.queries import ListMembersQuery as _ListMembersQuery

    members = await _list_members(
        _ListMembersQuery(tenant_id=tenant_id, actor_permissions=actor_permissions),
        uow=uow,
    )
    new_member = next((m for m in members if m["email"] == str(payload.email)), None)
    if new_member is None:  # pragma: no cover - shouldn't happen
        from ...core.errors import InternalError

        raise InternalError("Member not found after invite")
    return MemberOut(**new_member)


@router.patch(
    "/{tenant_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change member role",
)
async def change_member_role_endpoint(
    tenant_id: str,
    user_id: str,
    payload: ChangeRoleIn,
    uow: UnitOfWorkDep,
    actor_permissions: ActorPermissionsDep,
    actor_id: CurrentUserIdDep,
) -> None:
    cmd = ChangeMemberRoleCommand(
        tenant_id=tenant_id,
        user_id=user_id,
        new_role=payload.role,
        actor_id=actor_id,
    )
    await change_member_role(cmd, uow=uow, actor_permissions=actor_permissions)
    return None


@router.delete(
    "/{tenant_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove member",
)
async def remove_member_endpoint(
    tenant_id: str,
    user_id: str,
    uow: UnitOfWorkDep,
    actor_permissions: ActorPermissionsDep,
    actor_id: CurrentUserIdDep,
) -> None:
    cmd = RemoveMemberCommand(
        tenant_id=tenant_id,
        user_id=user_id,
        actor_id=actor_id,
    )
    await remove_member(cmd, uow=uow, actor_permissions=actor_permissions)
    return None


__all__ = ["Permission"]
