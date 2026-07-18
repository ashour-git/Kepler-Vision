"""Unit of Work.

The UoW wraps a single transaction and provides access to repositories.
On commit, in-memory outbox events are returned to the caller for
fan-out. (A persistent outbox table is added in a later sprint.)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING, Any

from sqlalchemy.ext.asyncio import AsyncSession

from ...domain.identity.events import DomainEvent
from .session import get_session_factory

if TYPE_CHECKING:
    from .repositories.tenant_repo import TenantRepository
    from .repositories.user_repo import UserRepository
    from .repositories.membership_repo import MembershipRepository
    from .repositories.api_key_repo import ApiKeyRepository
    from .repositories.audit_repo import AuditLogRepository
    from .repositories.refresh_token_repo import RefreshTokenRepository


class UnitOfWork(ABC):
    """Abstract UoW. Repos are attributes populated by the implementation."""

    users: "UserRepository"
    tenants: "TenantRepository"
    memberships: "MembershipRepository"
    api_keys: "ApiKeyRepository"
    audit_logs: "AuditLogRepository"
    refresh_tokens: "RefreshTokenRepository"

    @abstractmethod
    async def commit(self) -> list[DomainEvent]:
        """Commit the transaction and return the events emitted during it."""

    @abstractmethod
    async def rollback(self) -> None:
        """Roll back the transaction."""

    @abstractmethod
    async def flush(self) -> None:
        """Flush pending changes without committing."""

    @abstractmethod
    def collect_event(self, event: DomainEvent) -> None:
        """Record an event to be returned on commit."""


class SqlAlchemyUnitOfWork(UnitOfWork):
    """SQLAlchemy implementation of the UoW."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._events: list[DomainEvent] = []
        # Repos are imported lazily to avoid circular imports.
        from .repositories.tenant_repo import TenantRepository
        from .repositories.user_repo import UserRepository
        from .repositories.membership_repo import MembershipRepository
        from .repositories.api_key_repo import ApiKeyRepository
        from .repositories.audit_repo import AuditLogRepository
        from .repositories.refresh_token_repo import RefreshTokenRepository

        self.users = UserRepository(session)
        self.tenants = TenantRepository(session)
        self.memberships = MembershipRepository(session)
        self.api_keys = ApiKeyRepository(session)
        self.audit_logs = AuditLogRepository(session)
        self.refresh_tokens = RefreshTokenRepository(session)

    def collect_event(self, event: DomainEvent) -> None:
        self._events.append(event)

    async def flush(self) -> None:
        await self._session.flush()

    async def rollback(self) -> None:
        await self._session.rollback()

    async def commit(self) -> list[DomainEvent]:
        await self._session.commit()
        events = list(self._events)
        self._events.clear()
        return events

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> None:
        if exc_type is not None:
            await self.rollback()
        # Otherwise commit is called explicitly by the application layer.


@asynccontextmanager
async def uow() -> AsyncIterator[SqlAlchemyUnitOfWork]:
    """Async context manager that yields a UoW in a transaction.

    The session is committed when the UoW's `commit()` is called and rolled
    back automatically if the context exits with an exception.
    """
    factory = get_session_factory()
    async with factory() as session:
        unit = SqlAlchemyUnitOfWork(session)
        try:
            yield unit
        except Exception:
            await unit.rollback()
            raise
