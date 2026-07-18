"""Integration tests for the full auth flow.

These tests require Postgres + Redis. They are auto-skipped if the
services are not reachable, so the suite is friendly to local-only runs.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator

import httpx
import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config as AlembicConfig


# Use a dedicated database per test session
TEST_DB_NAME = f"kepler_test_{os.getpid()}"


async def _ensure_database() -> None:
    """Create the test database if it doesn't exist."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from sqlalchemy import text

    admin_url = f"postgresql+asyncpg://kepler:kepler@localhost:5432/postgres"
    test_url = f"postgresql+asyncpg://kepler:kepler@localhost:5432/{TEST_DB_NAME}"
    os.environ["DATABASE_URL"] = test_url
    os.environ["DATABASE_URL_SYNC"] = test_url.replace("+asyncpg", "+psycopg2")

    engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as conn:
            # Terminate any existing connections
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
    cfg = AlembicConfig("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL_SYNC"])
    command.upgrade(cfg, "head")


@pytest_asyncio.fixture(scope="session", autouse=True)
async def _bootstrap_database():
    if not os.environ.get("RUN_INTEGRATION"):
        yield
        return
    await _ensure_database()
    _run_migrations()
    yield


@pytest_asyncio.fixture
async def app_client(db_available: bool, redis_available: bool) -> AsyncIterator[httpx.AsyncClient]:
    if not (db_available and redis_available):
        pytest.skip("Postgres or Redis not reachable")
    from kepler.main import create_app

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


@pytest.mark.asyncio
async def test_healthz(app_client: httpx.AsyncClient) -> None:
    response = await app_client.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_signup_then_signin(app_client: httpx.AsyncClient, unique_email: str, strong_password: str) -> None:
    signup = await app_client.post(
        "/v1/auth/sign-up",
        json={
            "email": unique_email,
            "password": strong_password,
            "full_name": "Maya Rao",
            "tenant_name": "Maya's Workspace",
        },
    )
    assert signup.status_code == 201, signup.text
    body = signup.json()
    assert body["user"]["email"] == unique_email
    assert body["tenant"]["name"] == "Maya's Workspace"
    assert body["tokens"]["access_token"]
    assert body["tokens"]["refresh_token"]
    assert "user:read" in body["scopes"]

    # Sign in
    signin = await app_client.post(
        "/v1/auth/sign-in",
        json={"email": unique_email, "password": strong_password},
    )
    assert signin.status_code == 200, signin.text
    body2 = signin.json()
    assert body2["user"]["email"] == unique_email
    assert body2["role"] == "owner"


@pytest.mark.asyncio
async def test_signin_with_bad_password_returns_401(
    app_client: httpx.AsyncClient, unique_email: str, strong_password: str
) -> None:
    await app_client.post(
        "/v1/auth/sign-up",
        json={"email": unique_email, "password": strong_password},
    )
    response = await app_client.post(
        "/v1/auth/sign-in",
        json={"email": unique_email, "password": "wrong-password-1234"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "invalid_credentials"
    assert body["error"]["retryable"] is False


@pytest.mark.asyncio
async def test_refresh_rotates_tokens(
    app_client: httpx.AsyncClient, unique_email: str, strong_password: str
) -> None:
    signup = await app_client.post(
        "/v1/auth/sign-up",
        json={"email": unique_email, "password": strong_password},
    )
    tokens = signup.json()["tokens"]

    refresh = await app_client.post(
        "/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh.status_code == 200, refresh.text
    new_tokens = refresh.json()["tokens"]
    assert new_tokens["access_token"] != tokens["access_token"]
    assert new_tokens["refresh_token"] != tokens["refresh_token"]

    # Reuse of the old refresh should now fail
    reuse = await app_client.post(
        "/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert reuse.status_code == 401
    assert reuse.json()["error"]["code"] in ("token_reuse_detected", "unauthenticated")


@pytest.mark.asyncio
async def test_get_me_requires_auth(
    app_client: httpx.AsyncClient, unique_email: str, strong_password: str
) -> None:
    # No token
    no_auth = await app_client.get("/v1/users/me")
    assert no_auth.status_code == 401

    # With token
    signup = await app_client.post(
        "/v1/auth/sign-up",
        json={"email": unique_email, "password": strong_password},
    )
    access = signup.json()["tokens"]["access_token"]
    me = await app_client.get("/v1/users/me", headers={"Authorization": f"Bearer {access}"})
    assert me.status_code == 200
    body = me.json()
    assert body["user"]["email"] == unique_email
    assert body["default_role"] == "owner"
    assert "user:read" in body["scopes"]


@pytest.mark.asyncio
async def test_signup_password_too_short(app_client: httpx.AsyncClient, unique_email: str) -> None:
    response = await app_client.post(
        "/v1/auth/sign-up",
        json={"email": unique_email, "password": "short"},
    )
    assert response.status_code == 422  # Pydantic validation


@pytest.mark.asyncio
async def test_jwks_endpoint(app_client: httpx.AsyncClient) -> None:
    response = await app_client.get("/.well-known/jwks.json")
    assert response.status_code == 200
    body = response.json()
    assert "keys" in body
    assert len(body["keys"]) == 1
