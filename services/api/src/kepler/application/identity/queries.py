"""Identity use cases — queries (reads)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from ...core.errors import NotFoundError, PermissionError_, ValidationError
from ...domain.identity import (
    ApiKey,
    Email,
    Membership,
    Permission,
    Role,
    Tenant,
    TenantId,
    User,
    UserId,
    permissions_for_roles,
)
from ...infra.db.uow import UnitOfWork
from .commands import ApiKeyDTO, TenantDTO, UserDTO


@dataclass(frozen=True, slots=True)
class GetMeQuery:
    user_id: str


@dataclass(frozen=True, slots=True)
class GetMeResult:
    user: UserDTO
    memberships: list[dict[str, Any]]
    default_tenant: Optional[TenantDTO]
    default_role: Optional[str]
    scopes: list[str]


async def get_me(
    query: GetMeQuery,
    *,
    uow: UnitOfWork,
) -> GetMeResult:
    user = await uow.users.get_by_id(UserId(query.user_id))
    if user is None:
        raise NotFoundError("User not found")

    memberships = await uow.memberships.list_for_user(user.id)
    if not memberships:
        return GetMeResult(
            user=UserDTO.from_domain(user),
            memberships=[],
            default_tenant=None,
            default_role=None,
            scopes=[],
        )

    # Default to the most recent (last-created) membership.
    memberships_sorted = sorted(memberships, key=lambda m: m.created_at, reverse=True)
    default_membership = memberships_sorted[0]
    default_tenant = await uow.tenants.get_by_id(default_membership.tenant_id)
    if default_tenant is None:
        raise ValidationError("Default workspace not found")

    role = Role(default_membership.role)
    scopes = sorted(perm.value for perm in permissions_for_roles([role]))

    return GetMeResult(
        user=UserDTO.from_domain(user),
        memberships=[
            {
                "tenant_id": str(m.tenant_id),
                "role": m.role,
                "accepted_at": m.accepted_at.isoformat() if m.accepted_at else None,
                "created_at": m.created_at.isoformat(),
            }
            for m in memberships
        ],
        default_tenant=TenantDTO.from_domain(default_tenant),
        default_role=role.value,
        scopes=scopes,
    )


@dataclass(frozen=True, slots=True)
class ListMembersQuery:
    tenant_id: str
    actor_permissions: set[Permission]


async def list_members(
    query: ListMembersQuery,
    *,
    uow: UnitOfWork,
) -> list[dict[str, Any]]:
    if Permission.MEMBER_READ not in query.actor_permissions:
        raise PermissionError_("Cannot read members")

    memberships = await uow.memberships.list_for_tenant(TenantId(query.tenant_id))
    out: list[dict[str, Any]] = []
    for m in memberships:
        user = await uow.users.get_by_id(m.user_id)
        if user is None:
            continue
        out.append(
            {
                "user_id": str(m.user_id),
                "email": str(user.email),
                "full_name": user.full_name,
                "role": m.role,
                "joined_at": m.created_at.isoformat(),
                "accepted_at": m.accepted_at.isoformat() if m.accepted_at else None,
                "status": user.status.value,
            }
        )
    return out


@dataclass(frozen=True, slots=True)
class ListApiKeysQuery:
    user_id: str
    actor_permissions: set[Permission]


async def list_api_keys(
    query: ListApiKeysQuery,
    *,
    uow: UnitOfWork,
) -> list[ApiKeyDTO]:
    if Permission.APIKEY_READ not in query.actor_permissions:
        raise PermissionError_("Cannot read API keys")
    keys = await uow.api_keys.list_for_user(UserId(query.user_id))
    return [ApiKeyDTO.from_domain(k) for k in keys]
