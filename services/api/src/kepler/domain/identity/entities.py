"""Identity domain entities.

These are plain Python dataclasses; the persistence layer maps them to
SQLAlchemy ORM rows. Entities enforce invariants; they do not perform I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any, Optional

from ...core.time import utc_now
from .value_objects import ApiKeyId, Email, TenantId, UserId


class UserStatus(StrEnum):
    ACTIVE = "active"
    INVITED = "invited"
    DISABLED = "disabled"
    DELETED = "deleted"


class ApiKeyStatus(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


class TenantStatus(StrEnum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DELETED = "deleted"


class TenantPlan(StrEnum):
    FREE = "free"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    GOV = "gov"


@dataclass(slots=True)
class Tenant:
    """Top-level multi-tenant account."""

    id: TenantId
    name: str
    slug: str
    plan: TenantPlan
    status: TenantStatus
    region: str
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    deleted_at: Optional[datetime] = None

    def is_active(self) -> bool:
        return self.status == TenantStatus.ACTIVE


@dataclass(slots=True)
class User:
    """Global user account. Belongs to tenants via Membership."""

    id: UserId
    email: Email
    password_hash: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    locale: str = "en"
    timezone: str = "UTC"
    mfa_enabled: bool = False
    mfa_secret_enc: Optional[bytes] = None
    status: UserStatus = UserStatus.ACTIVE
    last_sign_in_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    deleted_at: Optional[datetime] = None

    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE and self.deleted_at is None

    def record_sign_in(self) -> None:
        self.last_sign_in_at = utc_now()

    def mark_deleted(self) -> None:
        self.status = UserStatus.DELETED
        self.deleted_at = utc_now()
        self.updated_at = utc_now()


@dataclass(slots=True)
class Membership:
    """Join row: user × tenant × role."""

    id: str
    user_id: UserId
    tenant_id: TenantId
    role: str
    created_at: datetime = field(default_factory=utc_now)
    invited_by: Optional[UserId] = None
    accepted_at: Optional[datetime] = None

    def accept(self) -> None:
        if self.accepted_at is None:
            self.accepted_at = utc_now()


@dataclass(slots=True)
class ApiKey:
    """API key credential for a user. Plaintext is shown only on create."""

    id: ApiKeyId
    user_id: UserId
    name: str
    key_prefix: str  # first 8 chars of the plaintext, for display
    key_hash: str  # argon2id of the full plaintext
    scopes: list[str] = field(default_factory=list)
    status: ApiKeyStatus = ApiKeyStatus.ACTIVE
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None
    created_at: datetime = field(default_factory=utc_now)
    revoked_at: Optional[datetime] = None

    def is_active(self) -> bool:
        if self.status != ApiKeyStatus.ACTIVE:
            return False
        if self.expires_at is not None and self.expires_at <= utc_now():
            return False
        return True

    def revoke(self) -> None:
        self.status = ApiKeyStatus.REVOKED
        self.revoked_at = utc_now()

    def to_summary(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "name": self.name,
            "key_prefix": self.key_prefix,
            "scopes": list(self.scopes),
            "status": self.status.value,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat(),
        }
