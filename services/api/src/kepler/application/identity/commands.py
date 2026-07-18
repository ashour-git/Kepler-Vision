"""Identity use cases — commands (mutations)."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Optional

from ...core.errors import (
    AccountDisabledError,
    AccountLockedError,
    AuthenticationError,
    ConflictError,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    NotFoundError,
    PermissionError_,
    RateLimitedError,
    TokenReuseError,
    ValidationError,
)
from ...core.ids import new_ulid
from ...core.security.jwt import (
    AccessTokenClaims,
    JWTService,
    RefreshTokenClaims,
)
from ...core.security.password import hash_password, needs_rehash, verify_password
from ...core.time import utc_now
from ...domain.identity import (
    ApiKey,
    ApiKeyId,
    ApiKeyStatus,
    Email,
    MembershipRemoved,
    MembershipRoleChanged,
    MembershipAdded,
    Password,
    Permission,
    Role,
    Tenant,
    TenantId,
    TenantPlan,
    TenantStatus,
    User,
    UserId,
    UserSignedIn,
    UserSignedOut,
    UserSignedUp,
    TokenRefreshed,
    TokenRevoked,
    is_valid_tenant_slug,
    password_meets_policy,
    permissions_for_roles,
)
from ...infra.cache.refresh_store import RefreshTokenStore
from ...infra.db.uow import UnitOfWork


# ---------------------------------------------------------------------------
# Result / command dataclasses (DTOs)
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Tokens:
    access_token: str
    access_expires_at: int  # unix seconds
    refresh_token: str
    refresh_expires_at: int  # unix seconds
    token_type: str = "Bearer"

    def to_dict(self) -> dict[str, Any]:
        return {
            "token_type": self.token_type,
            "access_token": self.access_token,
            "access_expires_at": self.access_expires_at,
            "refresh_token": self.refresh_token,
            "refresh_expires_at": self.refresh_expires_at,
        }


@dataclass(frozen=True, slots=True)
class UserDTO:
    id: str
    email: str
    full_name: Optional[str]
    avatar_url: Optional[str]
    locale: str
    timezone: str
    mfa_enabled: bool
    status: str
    created_at: str

    @classmethod
    def from_domain(cls, user: User) -> "UserDTO":
        return cls(
            id=str(user.id),
            email=str(user.email),
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            locale=user.locale,
            timezone=user.timezone,
            mfa_enabled=user.mfa_enabled,
            status=user.status.value,
            created_at=user.created_at.isoformat(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "email": self.email,
            "full_name": self.full_name,
            "avatar_url": self.avatar_url,
            "locale": self.locale,
            "timezone": self.timezone,
            "mfa_enabled": self.mfa_enabled,
            "status": self.status,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class TenantDTO:
    id: str
    name: str
    slug: str
    plan: str
    status: str
    region: str

    @classmethod
    def from_domain(cls, t: Tenant) -> "TenantDTO":
        return cls(
            id=str(t.id),
            name=t.name,
            slug=t.slug,
            plan=t.plan.value,
            status=t.status.value,
            region=t.region,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "plan": self.plan,
            "status": self.status,
            "region": self.region,
        }


@dataclass(frozen=True, slots=True)
class SignUpCommand:
    email: str
    password: str
    full_name: Optional[str] = None
    tenant_name: Optional[str] = None
    tenant_slug: Optional[str] = None
    region: str = "us-central1"


@dataclass(frozen=True, slots=True)
class SignUpResult:
    user: UserDTO
    tenant: TenantDTO
    tokens: Tokens
    scopes: list[str]


@dataclass(frozen=True, slots=True)
class SignInCommand:
    email: str
    password: str
    user_agent: Optional[str] = None
    ip: Optional[str] = None
    tenant_id: Optional[str] = None  # if omitted, picks the first membership


@dataclass(frozen=True, slots=True)
class SignInResult:
    user: UserDTO
    tenant: TenantDTO
    role: str
    tokens: Tokens
    scopes: list[str]


@dataclass(frozen=True, slots=True)
class RefreshCommand:
    refresh_token: str
    user_agent: Optional[str] = None
    ip: Optional[str] = None


@dataclass(frozen=True, slots=True)
class RefreshResult:
    tokens: Tokens
    user_id: str
    tenant_id: str
    role: str
    scopes: list[str]


@dataclass(frozen=True, slots=True)
class SignOutCommand:
    refresh_token: str
    user_id: str


@dataclass(frozen=True, slots=True)
class InviteMemberCommand:
    tenant_id: str
    email: str
    role: str
    invited_by: str
    full_name: Optional[str] = None


@dataclass(frozen=True, slots=True)
class ChangeMemberRoleCommand:
    tenant_id: str
    user_id: str
    new_role: str
    actor_id: str


@dataclass(frozen=True, slots=True)
class RemoveMemberCommand:
    tenant_id: str
    user_id: str
    actor_id: str


@dataclass(frozen=True, slots=True)
class CreateApiKeyCommand:
    user_id: str
    name: str
    scopes: list[str] = field(default_factory=list)
    expires_at: Optional[str] = None  # ISO 8601


@dataclass(frozen=True, slots=True)
class CreateApiKeyResult:
    api_key: Any  # ApiKey (DTO below)
    plaintext: str  # shown once


@dataclass(frozen=True, slots=True)
class ApiKeyDTO:
    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    status: str
    last_used_at: Optional[str]
    expires_at: Optional[str]
    created_at: str

    @classmethod
    def from_domain(cls, k: ApiKey) -> "ApiKeyDTO":
        return cls(
            id=str(k.id),
            name=k.name,
            key_prefix=k.key_prefix,
            scopes=list(k.scopes),
            status=k.status.value,
            last_used_at=k.last_used_at.isoformat() if k.last_used_at else None,
            expires_at=k.expires_at.isoformat() if k.expires_at else None,
            created_at=k.created_at.isoformat(),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "key_prefix": self.key_prefix,
            "scopes": self.scopes,
            "status": self.status,
            "last_used_at": self.last_used_at,
            "expires_at": self.expires_at,
            "created_at": self.created_at,
        }


@dataclass(frozen=True, slots=True)
class RevokeApiKeyCommand:
    user_id: str
    api_key_id: str


@dataclass(frozen=True, slots=True)
class ChangePasswordCommand:
    user_id: str
    current_password: str
    new_password: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ip_prefix(ip: Optional[str]) -> Optional[str]:
    if not ip:
        return None
    parts = ip.split(".")
    if len(parts) == 4:
        return ".".join(parts[:3]) + ".0"
    if ":" in ip:
        # IPv6: keep first 4 hextets
        return ":".join(ip.split(":")[:4])
    return ip


def _gen_api_key_plaintext() -> str:
    """Generate an API key: `kpk_<32 random base32 chars>`."""
    return "kpk_" + secrets.token_urlsafe(32)


def _hash_api_key(plaintext: str) -> tuple[str, str]:
    """Return (prefix, hash). Prefix is the first 12 chars (after `kpk_`).
    The hash is argon2id of the full plaintext.
    """
    prefix = plaintext[:12]
    return prefix, hash_password(plaintext)


async def _issue_tokens(
    *,
    user: User,
    tenant_id: TenantId,
    role: Role,
    jwt_service: JWTService,
    uow: UnitOfWork,
    refresh_store: RefreshTokenStore,
    user_agent: Optional[str],
    ip: Optional[str],
) -> Tokens:
    """Issue access + refresh tokens, persist the refresh, return both."""
    from ...settings import get_settings

    settings = get_settings()
    scopes = sorted(perm.value for perm in permissions_for_roles([role]))

    access_token, access_claims = jwt_service.issue_access(
        user_id=str(user.id),
        tenant_id=str(tenant_id),
        scopes=scopes,
        mfa=user.mfa_enabled,
    )
    refresh_token, refresh_claims = jwt_service.issue_refresh(
        user_id=str(user.id),
        family_id=new_ulid(),
    )

    expires_at = utc_now() + timedelta(seconds=settings.refresh_token_ttl_seconds)
    await uow.refresh_tokens.add(
        user_id=str(user.id),
        family_id=refresh_claims.family_id,
        jti=refresh_claims.jti,
        user_agent=user_agent,
        ip_prefix=_ip_prefix(ip),
        expires_at=expires_at,
    )

    return Tokens(
        access_token=access_token,
        access_expires_at=access_claims.exp,
        refresh_token=refresh_token,
        refresh_expires_at=refresh_claims.exp,
    )


# ---------------------------------------------------------------------------
# Sign up
# ---------------------------------------------------------------------------


async def sign_up(
    cmd: SignUpCommand,
    *,
    uow: UnitOfWork,
    jwt_service: JWTService,
    refresh_store: RefreshTokenStore,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> SignUpResult:
    """Create a new user + tenant, sign them in, return tokens."""
    email = Email(cmd.email)
    password = cmd.password
    if not password_meets_policy(password):
        raise ValidationError("Password does not meet policy", details={"field": "password"})

    tenant_name = cmd.tenant_name or email.value.split("@", 1)[0]
    if not tenant_name:
        raise ValidationError("Tenant name is required", details={"field": "tenant_name"})

    tenant_slug = cmd.tenant_slug
    if tenant_slug is None:
        # Derive from email local part
        local = email.value.split("@", 1)[0].replace(".", "-").replace("_", "-")
        base = local[:32] or "workspace"
        tenant_slug = base
    if not is_valid_tenant_slug(tenant_slug):
        raise ValidationError("Invalid tenant slug", details={"field": "tenant_slug"})

    user_id = UserId(new_ulid())
    tenant_id = TenantId(new_ulid())

    user = User(
        id=user_id,
        email=email,
        password_hash=hash_password(password),
        full_name=cmd.full_name,
    )
    tenant = Tenant(
        id=tenant_id,
        name=tenant_name,
        slug=tenant_slug,
        plan=TenantPlan.FREE,
        status=TenantStatus.ACTIVE,
        region=cmd.region,
    )

    try:
        await uow.tenants.add(tenant)
    except ConflictError as exc:
        # If the slug collides, try to make it unique by suffixing ULID
        suffix = new_ulid()[:8]
        tenant = Tenant(
            id=tenant_id,
            name=tenant_name,
            slug=f"{tenant_slug}-{suffix}"[:64],
            plan=TenantPlan.FREE,
            status=TenantStatus.ACTIVE,
            region=cmd.region,
        )
        await uow.tenants.add(tenant)

    try:
        await uow.users.add(user)
    except ConflictError as exc:
        raise EmailAlreadyExistsError("Email already registered", details={"field": "email"}) from exc

    # Owner of the new tenant
    await uow.memberships.add(
        user_id=user_id,
        tenant_id=tenant_id,
        role=Role.OWNER.value,
        invited_by=None,
    )

    # Audit
    await uow.audit_logs.append(
        tenant_id=tenant_id,
        actor_id=user_id,
        actor_type="user",
        action="identity.user.signed_up",
        resource_type="user",
        resource_id=str(user_id),
        metadata={"email": str(email), "tenant_id": str(tenant_id)},
        ip=ip,
        user_agent=user_agent,
    )

    uow.collect_event(
        UserSignedUp(user_id=user_id, tenant_id=tenant_id, actor_id=user_id)
    )

    role = Role.OWNER
    tokens = await _issue_tokens(
        user=user,
        tenant_id=tenant_id,
        role=role,
        jwt_service=jwt_service,
        uow=uow,
        refresh_store=refresh_store,
        user_agent=user_agent,
        ip=ip,
    )

    events = await uow.commit()
    # Events are normally dispatched via the outbox; nothing more here.
    del events

    return SignUpResult(
        user=UserDTO.from_domain(user),
        tenant=TenantDTO.from_domain(tenant),
        tokens=tokens,
        scopes=sorted(perm.value for perm in permissions_for_roles([role])),
    )


# ---------------------------------------------------------------------------
# Sign in
# ---------------------------------------------------------------------------


async def sign_in(
    cmd: SignInCommand,
    *,
    uow: UnitOfWork,
    jwt_service: JWTService,
    refresh_store: RefreshTokenStore,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> SignInResult:
    """Authenticate by email + password; issue tokens."""
    email_value = cmd.email.strip().lower()
    if not email_value:
        raise InvalidCredentialsError("Invalid credentials")

    # Lockout check
    locked_for = await refresh_store.is_locked_out(email_value)
    if locked_for is not None:
        raise AccountLockedError(
            "Account temporarily locked due to too many failed attempts",
            details={"retry_after_seconds": locked_for},
        )

    user = await uow.users.get_by_email(email_value)
    if user is None:
        # Constant-time-ish: still hash a dummy to avoid timing oracles
        verify_password(cmd.password, "$argon2id$v=19$m=65536,t=2,p=1$AAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA")
        await refresh_store.record_failed_login(email_value)
        raise InvalidCredentialsError("Invalid credentials")

    if not user.is_active():
        raise AccountDisabledError("Account is not active")

    if not verify_password(cmd.password, user.password_hash):
        attempts = await refresh_store.record_failed_login(email_value)
        if attempts >= _login_max_attempts():
            await refresh_store.set_lockout(email_value)
        raise InvalidCredentialsError("Invalid credentials")

    # Rehash on weak params
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(cmd.password)
        await uow.users.update(user)

    # Resolve membership
    memberships = await uow.memberships.list_for_user(user.id)
    if not memberships:
        raise AuthenticationError("No workspace membership found")

    if cmd.tenant_id:
        membership = next((m for m in memberships if str(m.tenant_id) == cmd.tenant_id), None)
        if membership is None:
            raise PermissionError_("You are not a member of this workspace")
    else:
        membership = memberships[0]

    role = Role(membership.role)
    tenant = await uow.tenants.get_by_id(membership.tenant_id)
    if tenant is None or not tenant.is_active():
        raise AuthenticationError("Workspace is not active")

    user.record_sign_in()
    await uow.users.update(user)

    await uow.audit_logs.append(
        tenant_id=tenant.id,
        actor_id=user.id,
        actor_type="user",
        action="identity.user.signed_in",
        resource_type="user",
        resource_id=str(user.id),
        ip=ip,
        user_agent=user_agent,
    )

    uow.collect_event(UserSignedIn(user_id=user.id, tenant_id=tenant.id, actor_id=user.id))

    tokens = await _issue_tokens(
        user=user,
        tenant_id=tenant.id,
        role=role,
        jwt_service=jwt_service,
        uow=uow,
        refresh_store=refresh_store,
        user_agent=user_agent,
        ip=ip,
    )

    await refresh_store.clear_failed_logins(email_value)
    await uow.commit()

    return SignInResult(
        user=UserDTO.from_domain(user),
        tenant=TenantDTO.from_domain(tenant),
        role=role.value,
        tokens=tokens,
        scopes=sorted(perm.value for perm in permissions_for_roles([role])),
    )


def _login_max_attempts() -> int:
    from ...settings import get_settings

    return get_settings().rate_limit_login_per_email


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------


async def refresh_session(
    cmd: RefreshCommand,
    *,
    uow: UnitOfWork,
    jwt_service: JWTService,
    refresh_store: RefreshTokenStore,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> RefreshResult:
    """Rotate a refresh token. Detects reuse; revokes family on theft."""
    claims = jwt_service.verify_refresh(cmd.refresh_token)

    # Family check
    if await uow.refresh_tokens.family_revoked(claims.family_id):
        raise TokenReuseError("Refresh family has been revoked")

    # Fast-path lock to prevent concurrent rotation
    lock = await refresh_store.try_lock_for_rotation(claims.jti, ttl_seconds=10)
    if not lock.acquired:
        # Another request is rotating; or this token has been used.
        if lock.already_used:
            await uow.refresh_tokens.revoke_family(claims.family_id)
            await uow.commit()
            raise TokenReuseError("Refresh token reuse detected; family revoked")
        raise AuthenticationError("Concurrent refresh attempt")

    try:
        # Look up the existing refresh record
        existing = await uow.refresh_tokens.get_by_jti(claims.jti)
        if existing is None:
            # Should not happen if the JWT was issued by us.
            await refresh_store.revoke(claims.jti, ttl_seconds=60)
            raise AuthenticationError("Unknown refresh token")
        if existing.used_at is not None or existing.revoked_at is not None:
            await uow.refresh_tokens.revoke_family(claims.family_id)
            await uow.commit()
            raise TokenReuseError("Refresh token reuse detected; family revoked")

        # Mark current token as used + revoked
        await uow.refresh_tokens.mark_used(claims.jti)
        await uow.refresh_tokens.revoke_jti(claims.jti)

        # Issue a new pair
        user = await uow.users.get_by_id(claims.sub)
        if user is None or not user.is_active():
            raise AuthenticationError("User not found or inactive")

        memberships = await uow.memberships.list_for_user(user.id)
        if not memberships:
            raise AuthenticationError("No workspace membership found")
        # Reuse the tenant from the access side: the family belongs to a tenant.
        # In our model the access token also carries `tid`; we re-derive it.
        # For simplicity, we pick the first membership.
        membership = memberships[0]
        role = Role(membership.role)

        tokens = await _issue_tokens(
            user=user,
            tenant_id=membership.tenant_id,
            role=role,
            jwt_service=jwt_service,
            uow=uow,
            refresh_store=refresh_store,
            user_agent=user_agent,
            ip=ip,
        )

        # Commit the lock acquisition (move to denylist)
        from ...settings import get_settings

        await refresh_store.commit_rotation(claims.jti, get_settings().refresh_token_ttl_seconds)

        uow.collect_event(TokenRefreshed(user_id=user.id, tenant_id=membership.tenant_id, actor_id=user.id, family_id=claims.family_id))

        await uow.commit()

        return RefreshResult(
            tokens=tokens,
            user_id=str(user.id),
            tenant_id=str(membership.tenant_id),
            role=role.value,
            scopes=sorted(perm.value for perm in permissions_for_roles([role])),
        )
    except Exception:
        await refresh_store.release_rotation_lock(claims.jti)
        raise


# ---------------------------------------------------------------------------
# Sign out
# ---------------------------------------------------------------------------


async def sign_out(
    cmd: SignOutCommand,
    *,
    uow: UnitOfWork,
    jwt_service: JWTService,
    refresh_store: RefreshTokenStore,
) -> None:
    """Revoke a refresh family."""
    try:
        claims = jwt_service.verify_refresh(cmd.refresh_token)
    except Exception:  # noqa: BLE001 - best effort
        # Even if the token is invalid/expired, we treat sign-out as idempotent.
        return

    count = await uow.refresh_tokens.revoke_family(claims.family_id)
    await refresh_store.revoke(claims.jti, ttl_seconds=60)
    uow.collect_event(
        TokenRevoked(
            user_id=UserId(claims.sub),
            family_id=claims.family_id,
            reason="user_signout",
        )
    )
    await uow.audit_logs.append(
        tenant_id=UserId(cmd.user_id),  # placeholder; tenant_id unknown at this point
        actor_id=UserId(cmd.user_id),
        actor_type="user",
        action="identity.user.signed_out",
        resource_type="user",
        resource_id=cmd.user_id,
    )
    del count
    await uow.commit()


# ---------------------------------------------------------------------------
# Members
# ---------------------------------------------------------------------------


async def invite_member(
    cmd: InviteMemberCommand,
    *,
    uow: UnitOfWork,
    actor_permissions: set[Permission],
) -> None:
    if Permission.MEMBER_INVITE not in actor_permissions:
        raise PermissionError_("Cannot invite members")

    valid_roles = {r.value for r in Role}
    if cmd.role not in valid_roles:
        raise ValidationError("Invalid role", details={"field": "role", "allowed": sorted(valid_roles)})

    # Create the user if they don't exist (or look up existing).
    email = Email(cmd.email)
    user = await uow.users.get_by_email(email)
    if user is None:
        # Provision an invited user with a random password they'll reset.
        user = User(
            id=UserId(new_ulid()),
            email=email,
            password_hash=hash_password(secrets.token_urlsafe(32)),
            full_name=cmd.full_name,
            status="invited",
        )
        await uow.users.add(user)

    existing = await uow.memberships.get(user.id, TenantId(cmd.tenant_id))
    if existing is not None:
        raise ConflictError("User is already a member of this workspace")

    await uow.memberships.add(
        user_id=user.id,
        tenant_id=TenantId(cmd.tenant_id),
        role=cmd.role,
        invited_by=UserId(cmd.invited_by),
    )
    uow.collect_event(
        MembershipAdded(
            user_id=user.id,
            tenant_id=TenantId(cmd.tenant_id),
            actor_id=UserId(cmd.invited_by),
            role=cmd.role,
        )
    )
    await uow.audit_logs.append(
        tenant_id=TenantId(cmd.tenant_id),
        actor_id=UserId(cmd.invited_by),
        actor_type="user",
        action="identity.membership.added",
        resource_type="user",
        resource_id=str(user.id),
        metadata={"role": cmd.role, "email": cmd.email},
    )
    await uow.commit()


async def change_member_role(
    cmd: ChangeMemberRoleCommand,
    *,
    uow: UnitOfWork,
    actor_permissions: set[Permission],
) -> None:
    if Permission.MEMBER_UPDATE not in actor_permissions:
        raise PermissionError_("Cannot change member roles")
    valid_roles = {r.value for r in Role}
    if cmd.new_role not in valid_roles:
        raise ValidationError("Invalid role", details={"field": "role", "allowed": sorted(valid_roles)})

    existing = await uow.memberships.get(UserId(cmd.user_id), TenantId(cmd.tenant_id))
    if existing is None:
        raise NotFoundError("Membership not found")
    if existing.role == "owner" and cmd.new_role != "owner":
        # Disallow demoting the last owner (skip complexity in MVP; in prod count owners).
        raise ValidationError("Cannot demote owner via this endpoint")

    updated = await uow.memberships.update_role(
        user_id=UserId(cmd.user_id),
        tenant_id=TenantId(cmd.tenant_id),
        role=cmd.new_role,
    )
    if updated is None:
        raise NotFoundError("Membership not found")

    uow.collect_event(
        MembershipRoleChanged(
            user_id=UserId(cmd.user_id),
            tenant_id=TenantId(cmd.tenant_id),
            actor_id=UserId(cmd.actor_id),
            old_role=existing.role,
            new_role=cmd.new_role,
        )
    )
    await uow.audit_logs.append(
        tenant_id=TenantId(cmd.tenant_id),
        actor_id=UserId(cmd.actor_id),
        actor_type="user",
        action="identity.membership.role_changed",
        resource_type="user",
        resource_id=cmd.user_id,
        metadata={"old_role": existing.role, "new_role": cmd.new_role},
    )
    await uow.commit()


async def remove_member(
    cmd: RemoveMemberCommand,
    *,
    uow: UnitOfWork,
    actor_permissions: set[Permission],
) -> None:
    if Permission.MEMBER_REMOVE not in actor_permissions:
        raise PermissionError_("Cannot remove members")

    existing = await uow.memberships.get(UserId(cmd.user_id), TenantId(cmd.tenant_id))
    if existing is None:
        raise NotFoundError("Membership not found")
    if existing.role == "owner":
        raise ValidationError("Cannot remove owner via this endpoint")

    ok = await uow.memberships.remove(
        user_id=UserId(cmd.user_id),
        tenant_id=TenantId(cmd.tenant_id),
    )
    if not ok:
        raise NotFoundError("Membership not found")

    uow.collect_event(
        MembershipRemoved(
            user_id=UserId(cmd.user_id),
            tenant_id=TenantId(cmd.tenant_id),
            actor_id=UserId(cmd.actor_id),
        )
    )
    await uow.audit_logs.append(
        tenant_id=TenantId(cmd.tenant_id),
        actor_id=UserId(cmd.actor_id),
        actor_type="user",
        action="identity.membership.removed",
        resource_type="user",
        resource_id=cmd.user_id,
        metadata={"role": existing.role},
    )
    await uow.commit()


# ---------------------------------------------------------------------------
# API keys
# ---------------------------------------------------------------------------


async def create_api_key(
    cmd: CreateApiKeyCommand,
    *,
    uow: UnitOfWork,
    actor_permissions: set[Permission],
) -> CreateApiKeyResult:
    if Permission.APIKEY_WRITE not in actor_permissions:
        raise PermissionError_("Cannot create API keys")

    plaintext = _gen_api_key_plaintext()
    prefix, key_hash = _hash_api_key(plaintext)
    api_key = ApiKey(
        id=ApiKeyId(new_ulid()),
        user_id=UserId(cmd.user_id),
        name=cmd.name,
        key_prefix=prefix,
        key_hash=key_hash,
        scopes=list(cmd.scopes),
    )
    await uow.api_keys.add(api_key)
    await uow.audit_logs.append(
        tenant_id=UserId(cmd.user_id),  # use user_id as the audit "tenant" placeholder
        actor_id=UserId(cmd.user_id),
        actor_type="user",
        action="identity.apikey.created",
        resource_type="api_key",
        resource_id=str(api_key.id),
        metadata={"name": cmd.name, "scopes": list(cmd.scopes)},
    )
    await uow.commit()
    return CreateApiKeyResult(api_key=ApiKeyDTO.from_domain(api_key), plaintext=plaintext)


async def revoke_api_key(
    cmd: RevokeApiKeyCommand,
    *,
    uow: UnitOfWork,
    actor_permissions: set[Permission],
) -> None:
    if Permission.APIKEY_REVOKE not in actor_permissions:
        raise PermissionError_("Cannot revoke API keys")
    revoked = await uow.api_keys.revoke(ApiKeyId(cmd.api_key_id))
    if revoked is None or str(revoked.user_id) != cmd.user_id:
        raise NotFoundError("API key not found")
    await uow.audit_logs.append(
        tenant_id=UserId(cmd.user_id),
        actor_id=UserId(cmd.user_id),
        actor_type="user",
        action="identity.apikey.revoked",
        resource_type="api_key",
        resource_id=cmd.api_key_id,
    )
    await uow.commit()


# ---------------------------------------------------------------------------
# Change password
# ---------------------------------------------------------------------------


async def change_password(
    cmd: ChangePasswordCommand,
    *,
    uow: UnitOfWork,
) -> None:
    if not password_meets_policy(cmd.new_password):
        raise ValidationError("Password does not meet policy", details={"field": "new_password"})

    user = await uow.users.get_by_id(UserId(cmd.user_id))
    if user is None:
        raise NotFoundError("User not found")
    if not verify_password(cmd.current_password, user.password_hash):
        raise InvalidCredentialsError("Current password is incorrect")

    user.password_hash = hash_password(cmd.new_password)
    await uow.users.update(user)
    await uow.audit_logs.append(
        tenant_id=user.id,
        actor_id=user.id,
        actor_type="user",
        action="identity.user.password_changed",
        resource_type="user",
        resource_id=str(user.id),
    )
    await uow.commit()
