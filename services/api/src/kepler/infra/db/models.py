"""ORM models for the identity context.

These are 1:1 with the domain entities. Mappers in the repository layer
convert between them.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import (
    ARRAY,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT, INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base, TimestampMixin


class TenantORM(Base, TimestampMixin):
    """tenants table."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    slug: Mapped[str] = mapped_column(Text, nullable=False)
    plan: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'free'"))
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'active'"))
    region: Mapped[str] = mapped_column(String(64), nullable=False, server_default=text("'us-central1'"))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    memberships: Mapped[list["MembershipORM"]] = relationship(back_populates="tenant", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("slug", name="tenants_slug_unique"),
        CheckConstraint(
            "plan IN ('free','pro','enterprise','gov')",
            name="tenants_plan_check",
        ),
        CheckConstraint(
            "status IN ('active','suspended','deleted')",
            name="tenants_status_check",
        ),
        Index("ix_tenants_status", "status"),
    )


class UserORM(Base, TimestampMixin):
    """users table."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    email: Mapped[str] = mapped_column(CITEXT(), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(Text)
    avatar_url: Mapped[Optional[str]] = mapped_column(Text)
    locale: Mapped[str] = mapped_column(String(16), nullable=False, server_default=text("'en'"))
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, server_default=text("'UTC'"))
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    mfa_secret_enc: Mapped[Optional[bytes]] = mapped_column()
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'active'"))
    last_sign_in_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    memberships: Mapped[list["MembershipORM"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    api_keys: Mapped[list["ApiKeyORM"]] = relationship(back_populates="user", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','invited','disabled','deleted')",
            name="users_status_check",
        ),
        Index("ix_users_status", "status"),
        Index("ix_users_last_sign_in_at", "last_sign_in_at"),
    )


class MembershipORM(Base, TimestampMixin):
    """memberships table."""

    __tablename__ = "memberships"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'member'"))
    invited_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    user: Mapped[UserORM] = relationship(back_populates="memberships", foreign_keys=[user_id])
    tenant: Mapped[TenantORM] = relationship(back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("user_id", "tenant_id", name="memberships_user_tenant_unique"),
        CheckConstraint(
            "role IN ('owner','admin','member','analyst','viewer','billing_admin','service')",
            name="memberships_role_check",
        ),
        Index("ix_memberships_tenant_role", "tenant_id", "role"),
        Index("ix_memberships_user", "user_id"),
    )


class ApiKeyORM(Base, TimestampMixin):
    """api_keys table."""

    __tablename__ = "api_keys"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(Text, nullable=False)
    scopes: Mapped[list[str]] = mapped_column(ARRAY(Text), nullable=False, server_default=text("'{}'"))
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'active'"))

    user: Mapped[UserORM] = relationship(back_populates="api_keys")

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','revoked')",
            name="api_keys_status_check",
        ),
        Index("ix_api_keys_user", "user_id"),
    )


class RefreshTokenORM(Base, TimestampMixin):
    """refresh_tokens table — tracks the active refresh token JTI per family."""

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    family_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    jti: Mapped[str] = mapped_column(String(64), nullable=False)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    ip_prefix: Mapped[Optional[str]] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    family_revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_refresh_tokens_user", "user_id"),
        Index("ix_refresh_tokens_family", "family_id"),
        Index("ix_refresh_tokens_jti", "jti"),
    )


class AuditLogORM(Base, TimestampMixin):
    """history table — append-only audit log."""

    __tablename__ = "history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=False
    )
    actor_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))
    actor_type: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'user'"))
    action: Mapped[str] = mapped_column(Text, nullable=False)
    resource_type: Mapped[Optional[str]] = mapped_column(String(64))
    resource_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    project_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    ip: Mapped[Optional[str]] = mapped_column(INET)
    user_agent: Mapped[Optional[str]] = mapped_column(Text)
    request_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))

    __table_args__ = (
        CheckConstraint(
            "actor_type IN ('user','service','system')",
            name="history_actor_type_check",
        ),
        Index("ix_history_tenant_created", "tenant_id", "created_at"),
        Index("ix_history_actor", "actor_id", "created_at"),
        Index("ix_history_resource", "resource_type", "resource_id", "created_at"),
        Index("ix_history_action", "action", "created_at"),
    )
