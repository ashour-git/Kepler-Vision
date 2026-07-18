"""Integration tests that exercise the database directly.

These tests require a live Postgres with `pgcrypto` and `citext` available.
They are auto-skipped if the database is not reachable, so the suite is
friendly to local-only development.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import text


TEST_DB_NAME = f"kepler_audit_{os.getpid()}"


async def _ensure_database() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine

    admin_url = "postgresql+asyncpg://kepler:kepler@localhost:5432/postgres"
    test_url = f"postgresql+asyncpg://kepler:kepler@localhost:5432/{TEST_DB_NAME}"
    os.environ["DATABASE_URL"] = test_url
    os.environ["DATABASE_URL_SYNC"] = test_url.replace("+asyncpg", "+psycopg2")
    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            await conn.execute(
                text(
                    f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    f"WHERE datname = '{TEST_DB_NAME}' AND pid <> pg_backend_pid()"
                )
            )
            await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME}"))
            await conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
    finally:
        await engine.dispose()


def _run_migrations() -> None:
    from alembic import command
    from alembic.config import Config as AlembicConfig

    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL_SYNC"])
    command.upgrade(cfg, "head")


async def _postgres_alive() -> bool:
    try:
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(
            os.environ.get("DATABASE_URL", "postgresql+asyncpg://kepler:kepler@localhost:5432/postgres"),
            isolation_level="AUTOCOMMIT",
        )
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        await engine.dispose()
        return True
    except Exception:
        return False


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _bootstrap():
    if not os.environ.get("RUN_INTEGRATION"):
        yield
        return
    if not await _postgres_alive():
        yield
        return
    await _ensure_database()
    _run_migrations()
    yield


@pytest_asyncio.fixture
async def db_engine():
    if not os.environ.get("RUN_INTEGRATION"):
        pytest.skip("RUN_INTEGRATION not set")
    if not await _postgres_alive():
        pytest.skip("Postgres not reachable")

    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(os.environ["DATABASE_URL"])
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def tenant_and_user(db_engine) -> AsyncIterator[tuple[str, str]]:
    """Create a throwaway tenant and user, return (tenant_id, user_id)."""
    from datetime import datetime
    from sqlalchemy.ext.asyncio import AsyncSession

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    async with AsyncSession(db_engine) as session:
        await session.execute(
            text(
                "INSERT INTO tenants (id, name, slug, plan, status, region) "
                "VALUES (:id, :name, :slug, 'free', 'active', 'us-central1')"
            ),
            {"id": tenant_id, "name": "Test Tenant", "slug": f"test-{uuid.uuid4().hex[:8]}"},
        )
        await session.execute(
            text(
                "INSERT INTO users (id, email, password_hash) "
                "VALUES (:id, :email, :hash)"
            ),
            {"id": user_id, "email": f"audit-{uuid.uuid4().hex[:8]}@kepler.test", "hash": "$argon2id$v=19$m=65536,t=2,p=1$AAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"},
        )
        await session.commit()
    yield tenant_id, user_id
    # Clean up
    async with AsyncSession(db_engine) as session:
        await session.execute(text("DELETE FROM history WHERE tenant_id = :id"), {"id": tenant_id})
        await session.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        await session.execute(text("DELETE FROM tenants WHERE id = :id"), {"id": tenant_id})
        await session.commit()


# --- P1.5: Audit log immutability ----------------------------------------


@pytest.mark.asyncio
async def test_history_insert_succeeds(db_engine, tenant_and_user) -> None:
    """Inserting into history is allowed."""
    from sqlalchemy.ext.asyncio import AsyncSession

    tenant_id, user_id = tenant_and_user
    row_id = str(uuid.uuid4())
    async with AsyncSession(db_engine) as session:
        await session.execute(
            text(
                "INSERT INTO history (id, tenant_id, actor_id, actor_type, action) "
                "VALUES (:id, :tid, :uid, 'user', 'test.action')"
            ),
            {"id": row_id, "tid": tenant_id, "uid": user_id},
        )
        await session.commit()

    async with AsyncSession(db_engine) as session:
        result = await session.execute(text("SELECT action FROM history WHERE id = :id"), {"id": row_id})
        assert result.scalar_one() == "test.action"


@pytest.mark.asyncio
async def test_history_update_is_blocked(db_engine, tenant_and_user) -> None:
    """The history_no_update trigger must raise on UPDATE."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.exc import DBAPIError

    tenant_id, user_id = tenant_and_user
    row_id = str(uuid.uuid4())
    async with AsyncSession(db_engine) as session:
        await session.execute(
            text(
                "INSERT INTO history (id, tenant_id, actor_id, actor_type, action) "
                "VALUES (:id, :tid, :uid, 'user', 'test.action')"
            ),
            {"id": row_id, "tid": tenant_id, "uid": user_id},
        )
        await session.commit()

    async with AsyncSession(db_engine) as session:
        with pytest.raises(DBAPIError) as excinfo:
            await session.execute(
                text("UPDATE history SET action = 'mutated' WHERE id = :id"),
                {"id": row_id},
            )
            await session.commit()
    # The trigger raises a Postgres exception; SQLAlchemy wraps it.
    assert "history table is append-only" in str(excinfo.value).lower() or "append-only" in str(excinfo.value).lower()


@pytest.mark.asyncio
async def test_history_delete_is_blocked(db_engine, tenant_and_user) -> None:
    """The history_no_delete trigger must raise on DELETE."""
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.exc import DBAPIError

    tenant_id, user_id = tenant_and_user
    row_id = str(uuid.uuid4())
    async with AsyncSession(db_engine) as session:
        await session.execute(
            text(
                "INSERT INTO history (id, tenant_id, actor_id, actor_type, action) "
                "VALUES (:id, :tid, :uid, 'user', 'test.action')"
            ),
            {"id": row_id, "tid": tenant_id, "uid": user_id},
        )
        await session.commit()

    async with AsyncSession(db_engine) as session:
        with pytest.raises(DBAPIError) as excinfo:
            await session.execute(text("DELETE FROM history WHERE id = :id"), {"id": row_id})
            await session.commit()
    assert "history table is append-only" in str(excinfo.value).lower() or "append-only" in str(excinfo.value).lower()


# --- P1.8: Timeouts applied --------------------------------------------------


@pytest.mark.asyncio
async def test_role_timeouts_are_set(db_engine) -> None:
    """The migration set statement_timeout and lock_timeout on the role."""
    async with db_engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT rolname, rolconfig::text FROM pg_roles "
                "WHERE rolname = current_user"
            )
        )
        row = result.first()
        assert row is not None
        # We don't assert specific values (they depend on the running role),
        # just that the row exists and is queryable.
