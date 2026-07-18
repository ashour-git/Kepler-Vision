"""Request-scoped FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Annotated, Any, Optional

from fastapi import Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.errors import (
    AuthenticationError,
    InvalidTokenError,
    NotFoundError,
    TokenExpiredError,
)
from ..core.security.jwt import (
    AccessTokenClaims,
    JWTService,
    get_jwt_service,
)
from ..domain.identity import Permission, Role, permissions_for_roles
from ..infra.cache.refresh_store import RefreshTokenStore, get_refresh_token_store
from ..infra.db.uow import UnitOfWork, uow

# -- DB / UoW --------------------------------------------------------------


async def _db_session_dep() -> AsyncIterator[AsyncSession]:
    async with get_db_session() as session:
        yield session


DbSessionDep = Annotated[AsyncSession, Depends(_db_session_dep)]


async def _uow_dep() -> AsyncIterator[UnitOfWork]:
    async with uow() as unit:
        yield unit


UnitOfWorkDep = Annotated[UnitOfWork, Depends(_uow_dep)]


# -- Singletons ------------------------------------------------------------


JWTServiceDep = Annotated[JWTService, Depends(get_jwt_service)]
RefreshTokenStoreDep = Annotated[RefreshTokenStore, Depends(get_refresh_token_store)]


# -- Auth ------------------------------------------------------------------


def _bearer_token(authorization: Optional[str]) -> str:
    if not authorization:
        raise AuthenticationError("Missing Authorization header")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise AuthenticationError("Invalid Authorization header")
    return parts[1]


def _extract_token(authorization: Optional[str]) -> tuple[str, str]:
    """Extract (token, scheme) from an Authorization header.

    Supported schemes:
      - Bearer <jwt>
      - ApiKey <kpk_...>
    """
    if not authorization:
        raise AuthenticationError("Missing Authorization header")
    parts = authorization.split(maxsplit=1)
    if len(parts) != 2:
        raise AuthenticationError("Invalid Authorization header")
    scheme, token = parts[0].lower(), parts[1].strip()
    if scheme not in ("bearer", "apikey"):
        raise AuthenticationError("Unsupported Authorization scheme")
    if not token:
        raise AuthenticationError("Empty token")
    return token, scheme


async def _authenticate_with_api_key(
    token: str,
    request: Request,
    jwt_service: JWTService,
) -> UserPrincipal:
    """Authenticate using an `ApiKey` (`kpk_…`).

    The plaintext token is matched by prefix (`key_prefix` is the first
    12 chars). We hash with argon2id and compare. On match we return a
    `UserPrincipal` representing the owning user.

    Side effects:
      - bumps `api_keys.last_used_at` (debounced via 60 s window per request)
    """
    from sqlalchemy import select
    import uuid as _uuid

    from ..core.security.password import verify_password
    from ..core.time import utc_now
    from ..infra.db.models import ApiKeyORM, UserORM
    from ..infra.db.session import get_session_factory

    if not token.startswith("kpk_") or len(token) < 12:
        raise AuthenticationError("Invalid API key")
    prefix = token[:12]

    factory = get_session_factory()
    async with factory() as session:
        stmt = select(ApiKeyORM).where(
            ApiKeyORM.key_prefix == prefix,
            ApiKeyORM.status == "active",
        )
        result = await session.execute(stmt)
        candidates = list(result.scalars().all())

    if not candidates:
        raise AuthenticationError("Invalid API key")

    matched: ApiKeyORM | None = None
    for row in candidates:
        if verify_password(token, row.key_hash):
            matched = row
            break
    if matched is None:
        raise AuthenticationError("Invalid API key")

    # Look up the owning user
    factory = get_session_factory()
    async with factory() as session:
        user_row = await session.get(UserORM, matched.user_id)
        if user_row is None or user_row.status != "active" or user_row.deleted_at is not None:
            raise AuthenticationError("API key owner is not active")
        # Debounce last_used_at updates
        now = utc_now()
        if matched.last_used_at is None or (now - matched.last_used_at).total_seconds() > 60:
            matched.last_used_at = now
            await session.commit()

    return UserPrincipal(
        user_id=str(user_row.id),
        tenant_id="",  # API key auth: tenant context comes from X-Tenant-Id header
        claims=None,  # type: ignore[arg-type]  # no JWT claims in API key mode
    )


async def _current_user(
    request: Request,
    authorization: Annotated[Optional[str], Header()] = None,
    x_tenant_id: Annotated[Optional[str], Header(alias="X-Tenant-Id")] = None,
    jwt_service: JWTServiceDep = None,  # type: ignore[assignment]
) -> UserPrincipal:
    """Resolve the access token (or API key) to a `UserPrincipal`."""
    from ..domain.identity import Email, User, UserId

    token, scheme = _extract_token(authorization)
    if scheme == "apikey":
        principal = await _authenticate_with_api_key(token, request, jwt_service)
        # For API key auth, the tenant context comes from X-Tenant-Id
        if x_tenant_id:
            principal = UserPrincipal(
                user_id=principal.user_id,
                tenant_id=x_tenant_id,
                claims=principal.claims,
            )
        if not principal.tenant_id:
            raise AuthenticationError("X-Tenant-Id header is required for API key auth")
        request.state.user_id = principal.user_id
        request.state.tenant_id = principal.tenant_id
        return principal

    try:
        claims: AccessTokenClaims = jwt_service.verify_access(token, audience="kepler.web")
    except TokenExpiredError:
        raise
    except InvalidTokenError as exc:
        raise AuthenticationError(str(exc.message)) from exc

    # We need a sync DB read here; use the session from the request.
    from ..infra.db.session import get_session_factory

    factory = get_session_factory()
    async with factory() as session:
        # Use a tiny inline lookup — keeps the dependency self-contained.
        from sqlalchemy import select
        import uuid as _uuid

        from ..infra.db.models import UserORM

        stmt = select(UserORM).where(
            UserORM.id == _uuid.UUID(claims.sub), UserORM.deleted_at.is_(None)
        )
        result = await session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise AuthenticationError("User not found")
        if row.status != "active":
            raise AuthenticationError("User is not active")

    principal = UserPrincipal(
        user_id=claims.sub,
        tenant_id=claims.tenant_id,
        claims=claims,
    )
    request.state.user_id = principal.user_id
    request.state.tenant_id = principal.tenant_id
    return principal


@dataclass
class UserPrincipal:  # noqa: D401 - simple holder
    """Request-scoped principal extracted from the access token."""

    user_id: str
    tenant_id: str
    claims: AccessTokenClaims

    # Pydantic can't introspect a stdlib dataclass; we keep it a
    # dataclass and use `response_model=None` on the endpoints that
    # return it (none do — the API returns Pydantic DTOs only).


CurrentUserDep = Annotated[UserPrincipal, Depends(_current_user)]
CurrentUserIdDep = Annotated[str, Depends(lambda p=CurrentUserDep: p.user_id)]
CurrentTenantIdDep = Annotated[str, Depends(lambda p=CurrentUserDep: p.tenant_id)]


def _scopes_to_permissions(scopes: tuple[str, ...]) -> set[Permission]:
    """Map OAuth-style scopes to Permission enum values.

    For MVP, scopes are identical to permission keys. Unknown scopes are
    silently ignored — the role's permissions are the source of truth.
    """
    out: set[Permission] = set()
    known = {p.value for p in Permission}
    for s in scopes:
        if s in known:
            out.add(Permission(s))
    return out


async def _actor_permissions(
    request: Request,
    principal: CurrentUserDep,
    uow: UnitOfWorkDep,
) -> set[Permission]:
    """Resolve the principal's roles into a set of permissions."""
    roles = await _resolve_roles(principal.user_id, principal.tenant_id, uow)
    return permissions_for_roles(roles)


async def _resolve_roles(
    user_id: str, tenant_id: str, uow: UnitOfWork
) -> list[Role]:
    from ..domain.identity import TenantId, UserId

    membership = await uow.memberships.get(UserId(user_id), TenantId(tenant_id))
    if membership is None:
        raise NotFoundError("Membership not found for current tenant")
    role = _safe_role(membership.role)
    if role is None:
        raise NotFoundError("Unknown role")
    return [role]


def _safe_role(value: str) -> Optional[Role]:
    try:
        return Role(value)
    except ValueError:
        return None


ActorPermissionsDep = Annotated[set[Permission], Depends(_actor_permissions)]


# -- Imports needed for dataclass-like field used above ---------------------
from dataclasses import dataclass  # noqa: E402
