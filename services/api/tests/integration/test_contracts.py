"""End-to-end contract tests for the auth subsystem.

These tests exercise the full HTTP stack against a real Postgres and
Redis. They are auto-skipped when the services are unreachable so the
suite is friendly to local-only development.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio

# Force the test database before any kepler import.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("LOG_FORMAT", "console")


TEST_DB_NAME = f"kepler_contract_{os.getpid()}"


async def _ensure_database() -> None:
    from sqlalchemy import text
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


async def _redis_alive() -> bool:
    try:
        import redis.asyncio as redis

        client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/2"))
        await client.ping()
        await client.aclose()
        return True
    except Exception:
        return False


async def _postgres_alive() -> bool:
    try:
        from sqlalchemy import text
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
    pg_alive = await _postgres_alive()
    rd_alive = await _redis_alive()
    if not (pg_alive and rd_alive):
        yield
        return
    await _ensure_database()
    _run_migrations()
    yield


@pytest_asyncio.fixture
async def app_client() -> AsyncIterator[httpx.AsyncClient]:
    pg_alive = await _postgres_alive()
    rd_alive = await _redis_alive()
    if not (pg_alive and rd_alive):
        pytest.skip("Postgres or Redis not reachable")

    # Reset Redis state
    import redis.asyncio as redis

    client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/2"))
    await client.flushdb()
    await client.aclose()

    # Reset cached singletons
    from kepler.core.security.jwt import reset_jwt_service
    from kepler.infra.cache.redis import reset_redis_client
    from kepler.infra.cache.refresh_store import reset_refresh_token_store
    from kepler.infra.db.session import reset_session_factory
    from kepler.settings import reset_settings_cache

    reset_settings_cache()
    reset_jwt_service()
    reset_redis_client()
    reset_refresh_token_store()
    reset_session_factory()

    from kepler.main import create_app

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


# --- Happy-path contract ---------------------------------------------------


@pytest.mark.asyncio
async def test_signup_signin_refresh_logout_roundtrip(app_client: httpx.AsyncClient) -> None:
    email = f"user-{uuid.uuid4().hex[:12]}@kepler.test"
    password = "KeplerStrongPass!2026XYZ"

    # Sign-up
    signup = await app_client.post(
        "/v1/auth/sign-up",
        json={"email": email, "password": password, "full_name": "Maya Rao"},
    )
    assert signup.status_code == 201, signup.text
    body = signup.json()
    assert body["user"]["email"] == email
    assert body["tenant"]["name"] == "Maya Rao"
    assert body["tokens"]["access_token"]
    assert body["tokens"]["refresh_token"]
    assert "user:read" in body["scopes"]
    signup_access = body["tokens"]["access_token"]
    signup_refresh = body["tokens"]["refresh_token"]

    # /me with the access token
    me = await app_client.get("/v1/users/me", headers={"Authorization": f"Bearer {signup_access}"})
    assert me.status_code == 200, me.text
    assert me.json()["user"]["email"] == email
    assert me.json()["default_role"] == "owner"

    # Refresh
    refreshed = await app_client.post(
        "/v1/auth/refresh",
        json={"refresh_token": signup_refresh},
    )
    assert refreshed.status_code == 200, refreshed.text
    new_tokens = refreshed.json()["tokens"]
    assert new_tokens["access_token"] != signup_access

    # Sign-out
    signout = await app_client.post(
        "/v1/auth/sign-out",
        json={"refresh_token": signup_refresh},
        headers={"Authorization": f"Bearer {new_tokens['access_token']}"},
    )
    assert signout.status_code == 204

    # Reuse of the old refresh should fail
    reuse = await app_client.post(
        "/v1/auth/refresh",
        json={"refresh_token": signup_refresh},
    )
    assert reuse.status_code == 401


@pytest.mark.asyncio
async def test_api_key_lifecycle(app_client: httpx.AsyncClient) -> None:
    email = f"user-{uuid.uuid4().hex[:12]}@kepler.test"
    password = "KeplerStrongPass!2026XYZ"
    signup = await app_client.post(
        "/v1/auth/sign-up",
        json={"email": email, "password": password},
    )
    assert signup.status_code == 201, signup.text
    access = signup.json()["tokens"]["access_token"]

    # Create API key
    create = await app_client.post(
        "/v1/users/me/api-keys",
        json={"name": "ci-runner", "scopes": ["user:read"]},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["api_key"]["name"] == "ci-runner"
    plaintext = body["plaintext"]
    assert plaintext.startswith("kpk_")

    # List keys
    listed = await app_client.get(
        "/v1/users/me/api-keys",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert listed.status_code == 200
    assert any(k["name"] == "ci-runner" for k in listed.json())

    # Revoke
    key_id = body["api_key"]["id"]
    revoked = await app_client.delete(
        f"/v1/users/me/api-keys/{key_id}",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert revoked.status_code == 204

    # Confirm revoked
    listed2 = await app_client.get(
        "/v1/users/me/api-keys",
        headers={"Authorization": f"Bearer {access}"},
    )
    assert all(k["status"] == "revoked" for k in listed2.json() if k["id"] == key_id)


@pytest.mark.asyncio
async def test_members_invite_and_role_change(app_client: httpx.AsyncClient) -> None:
    owner_email = f"owner-{uuid.uuid4().hex[:12]}@kepler.test"
    password = "KeplerStrongPass!2026XYZ"
    signup = await app_client.post(
        "/v1/auth/sign-up",
        json={"email": owner_email, "password": password},
    )
    assert signup.status_code == 201
    owner_access = signup.json()["tokens"]["access_token"]
    tenant_id = signup.json()["tenant"]["id"]

    member_email = f"member-{uuid.uuid4().hex[:12]}@kepler.test"
    invite = await app_client.post(
        f"/v1/workspaces/{tenant_id}/members",
        json={"email": member_email, "role": "viewer"},
        headers={"Authorization": f"Bearer {owner_access}"},
    )
    assert invite.status_code == 201, invite.text
    assert invite.json()["email"] == member_email
    member_id = invite.json()["user_id"]

    # List
    listed = await app_client.get(
        f"/v1/workspaces/{tenant_id}/members",
        headers={"Authorization": f"Bearer {owner_access}"},
    )
    assert listed.status_code == 200
    assert any(m["user_id"] == member_id for m in listed.json())

    # Promote
    patch = await app_client.patch(
        f"/v1/workspaces/{tenant_id}/members/{member_id}",
        json={"role": "analyst"},
        headers={"Authorization": f"Bearer {owner_access}"},
    )
    assert patch.status_code == 204

    # Remove
    delete = await app_client.delete(
        f"/v1/workspaces/{tenant_id}/members/{member_id}",
        headers={"Authorization": f"Bearer {owner_access}"},
    )
    assert delete.status_code == 204


@pytest.mark.asyncio
async def test_password_change_revocates_session(app_client: httpx.AsyncClient) -> None:
    email = f"user-{uuid.uuid4().hex[:12]}@kepler.test"
    password = "KeplerStrongPass!2026XYZ"
    new_password = "KeplerDifferentPass!2026ABC"
    signup = await app_client.post(
        "/v1/auth/sign-up",
        json={"email": email, "password": password},
    )
    access = signup.json()["tokens"]["access_token"]
    change = await app_client.post(
        "/v1/users/me/change-password",
        json={"current_password": password, "new_password": new_password},
        headers={"Authorization": f"Bearer {access}"},
    )
    assert change.status_code == 204

    # Old password should no longer work
    bad = await app_client.post(
        "/v1/auth/sign-in",
        json={"email": email, "password": password},
    )
    assert bad.status_code == 401

    # New password works
    good = await app_client.post(
        "/v1/auth/sign-in",
        json={"email": email, "password": new_password},
    )
    assert good.status_code == 200


@pytest.mark.asyncio
async def test_rate_limiting_on_failed_logins(app_client: httpx.AsyncClient) -> None:
    email = f"user-{uuid.uuid4().hex[:12]}@kepler.test"
    password = "KeplerStrongPass!2026XYZ"
    # Sign up first to ensure the user exists
    await app_client.post("/v1/auth/sign-up", json={"email": email, "password": password})

    # 5 wrong attempts → 6th should be locked
    for _ in range(5):
        bad = await app_client.post(
            "/v1/auth/sign-in",
            json={"email": email, "password": "wrong-password-1234"},
        )
        assert bad.status_code == 401

    locked = await app_client.post(
        "/v1/auth/sign-in",
        json={"email": email, "password": password},
    )
    assert locked.status_code == 401
    assert locked.json()["error"]["code"] in ("account_locked", "invalid_credentials")


@pytest.mark.asyncio
async def test_healthz_and_jwks(app_client: httpx.AsyncClient) -> None:
    h = await app_client.get("/healthz")
    assert h.status_code == 200
    r = await app_client.get("/.well-known/jwks.json")
    assert r.status_code == 200
    assert "keys" in r.json()
    assert len(r.json()["keys"]) == 1
