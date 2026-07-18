"""Async SQLAlchemy engine + session factory.

The session factory is created once per process and cached. Tests can
reset the factory between runs.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from ...settings import Settings, get_settings

_engine: Optional[AsyncEngine] = None
_session_factory: Optional[async_sessionmaker[AsyncSession]] = None


def _build_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(
        settings.database_url,
        pool_size=settings.database_pool_size,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
        echo=settings.database_echo,
        future=True,
    )


def get_engine() -> AsyncEngine:
    """Return the process-wide async engine, creating it on first use."""
    global _engine
    if _engine is None:
        _engine = _build_engine(get_settings())
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the process-wide session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
            class_=AsyncSession,
        )
    return _session_factory


def create_async_engine_for(settings: Settings) -> AsyncEngine:
    """Build a fresh engine (used in tests)."""
    return _build_engine(settings)


def create_async_session_factory(settings: Settings) -> async_sessionmaker[AsyncSession]:
    """Build a fresh session factory (used in tests)."""
    return async_sessionmaker(
        bind=_build_engine(settings),
        expire_on_commit=False,
        autoflush=False,
        class_=AsyncSession,
    )


def reset_session_factory() -> None:
    """Drop cached engine + factory. Used in tests."""
    global _engine, _session_factory
    if _engine is not None:
        # AsyncEngine.dispose is sync (it returns a coroutine, but we just call it)
        try:
            _engine.sync_engine.dispose(close=True)
        except Exception:  # noqa: BLE001 - best effort
            pass
    _engine = None
    _session_factory = None


@asynccontextmanager
async def get_db_session() -> AsyncIterator[AsyncSession]:
    """Yield a session within a transaction. Commits on success, rolls back on error."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
