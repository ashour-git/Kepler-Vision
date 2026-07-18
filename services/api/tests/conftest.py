"""Shared pytest fixtures.

For local development without Docker, the `unit` tests use mocks where
needed. Integration tests require Postgres + Redis (the docker-compose
stack in `docker-compose.yml`). They are auto-skipped if the services
are unreachable, so the suite is friendly to local-only runs.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Optional

import pytest
import pytest_asyncio

# Force test settings before anything else loads the env
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_FORMAT", "console")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get("TEST_DATABASE_URL", "postgresql+asyncpg://kepler:kepler@localhost:5432/kepler_test"),
)
os.environ.setdefault(
    "DATABASE_URL_SYNC",
    os.environ.get("TEST_DATABASE_URL_SYNC", "postgresql+psycopg2://kepler:kepler@localhost:5432/kepler_test"),
)
os.environ.setdefault("REDIS_URL", os.environ.get("TEST_REDIS_URL", "redis://localhost:6379/1"))


@pytest.fixture(scope="session")
def event_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
def _reset_settings_cache() -> None:
    from kepler.settings import get_settings, reset_settings_cache

    reset_settings_cache()
    get_settings()


@pytest_asyncio.fixture
async def db_available() -> bool:
    """Probe Postgres. Integration tests are skipped if unreachable."""
    try:
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text

        engine = create_async_engine(os.environ["DATABASE_URL"])
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True
    except Exception:
        return False


@pytest_asyncio.fixture
async def redis_available() -> bool:
    """Probe Redis. Integration tests are skipped if unreachable."""
    try:
        import redis.asyncio as redis

        client = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
        await client.ping()
        await client.aclose()
        return True
    except Exception:
        return False


@pytest.fixture
def unique_email() -> str:
    """A fresh email per test."""
    return f"user-{uuid.uuid4().hex[:12]}@kepler.test"


@pytest.fixture
def strong_password() -> str:
    return "KeplerStrongPass!2026XYZ"


@pytest_asyncio.fixture
async def redis_client():
    """Yield a Redis client, scoped to the test, and flush the DB on teardown."""
    import redis.asyncio as redis

    client = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
    await client.flushdb()
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()
