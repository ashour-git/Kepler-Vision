"""Mappers between domain entities and ORM rows.

Keep mappers explicit and well-tested. They are the only place that knows
the shape of both layers.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Optional

from ...core.ids import parse_ulid
from ...domain.identity.entities import (
    ApiKey,
    ApiKeyStatus,
    Membership,
    Tenant,
    TenantPlan,
    TenantStatus,
    User,
    UserStatus,
)
from ...domain.identity.value_objects import ApiKeyId, Email, TenantId, UserId
from .models import ApiKeyORM, MembershipORM, TenantORM, UserORM


def _ensure_aware(value: datetime) -> datetime:
    """SQLAlchemy may return naive datetimes; coerce to UTC-aware."""
    if value.tzinfo is None:
        return value.replace(tzinfo=__import__("datetime").UTC)
    return value


# --- Tenant ----------------------------------------------------------------


def tenant_to_orm(t: Tenant) -> TenantORM:
    return TenantORM(
        id=uuid.UUID(str(t.id)),
        name=t.name,
        slug=t.slug,
        plan=t.plan.value,
        status=t.status.value,
        region=t.region,
        created_at=t.created_at,
        updated_at=t.updated_at,
        deleted_at=t.deleted_at,
    )


def tenant_to_domain(row: TenantORM) -> Tenant:
    return Tenant(
        id=TenantId(str(row.id)),
        name=row.name,
        slug=row.slug,
        plan=TenantPlan(row.plan),
        status=TenantStatus(row.status),
        region=row.region,
        created_at=_ensure_aware(row.created_at),
        updated_at=_ensure_aware(row.updated_at),
        deleted_at=_ensure_aware(row.deleted_at) if row.deleted_at else None,
    )


# --- User ------------------------------------------------------------------


def user_to_orm(u: User) -> UserORM:
    return UserORM(
        id=uuid.UUID(str(u.id)),
        email=str(u.email),
        password_hash=u.password_hash,
        full_name=u.full_name,
        avatar_url=u.avatar_url,
        locale=u.locale,
        timezone=u.timezone,
        mfa_enabled=u.mfa_enabled,
        mfa_secret_enc=u.mfa_secret_enc,
        status=u.status.value,
        last_sign_in_at=u.last_sign_in_at,
        created_at=u.created_at,
        updated_at=u.updated_at,
        deleted_at=u.deleted_at,
    )


def user_to_domain(row: UserORM) -> User:
    return User(
        id=UserId(str(row.id)),
        email=Email(str(row.email)),
        password_hash=row.password_hash,
        full_name=row.full_name,
        avatar_url=row.avatar_url,
        locale=row.locale,
        timezone=row.timezone,
        mfa_enabled=row.mfa_enabled,
        mfa_secret_enc=row.mfa_secret_enc,
        status=UserStatus(row.status),
        last_sign_in_at=_ensure_aware(row.last_sign_in_at) if row.last_sign_in_at else None,
        created_at=_ensure_aware(row.created_at),
        updated_at=_ensure_aware(row.updated_at),
        deleted_at=_ensure_aware(row.deleted_at) if row.deleted_at else None,
    )


# --- Membership ------------------------------------------------------------


def membership_to_orm(m: Membership) -> MembershipORM:
    return MembershipORM(
        id=uuid.UUID(m.id) if _looks_like_uuid(m.id) else uuid.uuid4(),
        user_id=uuid.UUID(str(m.user_id)),
        tenant_id=uuid.UUID(str(m.tenant_id)),
        role=m.role,
        invited_by=uuid.UUID(str(m.invited_by)) if m.invited_by else None,
        accepted_at=m.accepted_at,
        created_at=m.created_at,
    )


def membership_to_domain(row: MembershipORM) -> Membership:
    return Membership(
        id=str(row.id),
        user_id=UserId(str(row.user_id)),
        tenant_id=TenantId(str(row.tenant_id)),
        role=row.role,
        created_at=_ensure_aware(row.created_at),
        invited_by=UserId(str(row.invited_by)) if row.invited_by else None,
        accepted_at=_ensure_aware(row.accepted_at) if row.accepted_at else None,
    )


# --- API Key ---------------------------------------------------------------


def api_key_to_orm(k: ApiKey) -> ApiKeyORM:
    return ApiKeyORM(
        id=uuid.UUID(str(k.id)),
        user_id=uuid.UUID(str(k.user_id)),
        name=k.name,
        key_prefix=k.key_prefix,
        key_hash=k.key_hash,
        scopes=list(k.scopes),
        status=k.status.value,
        expires_at=k.expires_at,
        last_used_at=k.last_used_at,
        created_at=k.created_at,
        revoked_at=k.revoked_at,
    )


def api_key_to_domain(row: ApiKeyORM) -> ApiKey:
    return ApiKey(
        id=ApiKeyId(str(row.id)),
        user_id=UserId(str(row.user_id)),
        name=row.name,
        key_prefix=row.key_prefix,
        key_hash=row.key_hash,
        scopes=list(row.scopes or []),
        status=ApiKeyStatus(row.status),
        expires_at=_ensure_aware(row.expires_at) if row.expires_at else None,
        last_used_at=_ensure_aware(row.last_used_at) if row.last_used_at else None,
        created_at=_ensure_aware(row.created_at),
        revoked_at=_ensure_aware(row.revoked_at) if row.revoked_at else None,
    )


# --- helpers ---------------------------------------------------------------


def _looks_like_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError, TypeError):
        return False


__all__ = [
    "tenant_to_domain",
    "tenant_to_orm",
    "user_to_domain",
    "user_to_orm",
    "membership_to_domain",
    "membership_to_orm",
    "api_key_to_domain",
    "api_key_to_orm",
]
