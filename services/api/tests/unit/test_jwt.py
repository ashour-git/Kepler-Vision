"""Unit tests for the JWT service."""

from __future__ import annotations

import time

import pytest

from kepler.core.errors import TokenExpiredError
from kepler.core.security.jwt import (
    AccessTokenClaims,
    JWTService,
    RefreshTokenClaims,
)
from kepler.settings import Settings


@pytest.fixture
def jwt_service(tmp_path) -> JWTService:
    # Use a per-test private/public key path to keep state clean.
    settings = Settings(
        app_env="test",
        jwt_private_key_path=str(tmp_path / "priv.pem"),
        jwt_public_key_path=str(tmp_path / "pub.pem"),
        access_token_ttl_seconds=60,
        refresh_token_ttl_seconds=3600,
    )
    return JWTService(settings)


def test_issue_and_verify_access(jwt_service: JWTService) -> None:
    token, claims = jwt_service.issue_access(
        user_id="00000000-0000-0000-0000-000000000001",
        tenant_id="00000000-0000-0000-0000-000000000002",
        scopes=["user:read", "workspace:read"],
        mfa=False,
    )
    assert isinstance(token, str)
    assert "." in token  # JWT shape
    # P1.1: explicit audience required; default is kepler.web
    verified = jwt_service.verify_access(token, audience="kepler.web")
    assert isinstance(verified, AccessTokenClaims)
    assert verified.sub == "00000000-0000-0000-0000-000000000001"
    assert verified.tenant_id == "00000000-0000-0000-0000-000000000002"
    assert verified.scopes == ("user:read", "workspace:read")
    assert verified.aud == "kepler.web"
    assert verified.iss == "kepler.api"


def test_verify_access_rejects_wrong_audience(jwt_service: JWTService) -> None:
    """A token issued for one audience must not be accepted by another."""
    token, _ = jwt_service.issue_access(
        user_id="00000000-0000-0000-0000-000000000001",
        tenant_id="00000000-0000-0000-0000-000000000002",
        scopes=[],
    )
    with pytest.raises(Exception):
        jwt_service.verify_access(token, audience="kepler.cli")


def test_issue_and_verify_refresh(jwt_service: JWTService) -> None:
    token, claims = jwt_service.issue_refresh(
        user_id="00000000-0000-0000-0000-000000000001",
        family_id="00000000-0000-0000-0000-000000000003",
    )
    verified = jwt_service.verify_refresh(token)
    assert isinstance(verified, RefreshTokenClaims)
    assert verified.family_id == "00000000-0000-0000-0000-000000000003"
    assert verified.sub == "00000000-0000-0000-0000-000000000001"


def test_refresh_cannot_be_used_as_access(jwt_service: JWTService) -> None:
    token, _ = jwt_service.issue_refresh(
        user_id="00000000-0000-0000-0000-000000000001",
        family_id="00000000-0000-0000-0000-000000000003",
    )
    with pytest.raises(Exception):
        jwt_service.verify_access(token)


def test_access_cannot_be_used_as_refresh(jwt_service: JWTService) -> None:
    token, _ = jwt_service.issue_access(
        user_id="00000000-0000-0000-0000-000000000001",
        tenant_id="00000000-0000-0000-0000-000000000002",
        scopes=[],
    )
    with pytest.raises(Exception):
        jwt_service.verify_refresh(token)


def test_expired_token_raises_token_expired(tmp_path) -> None:
    settings = Settings(
        app_env="test",
        jwt_private_key_path=str(tmp_path / "priv.pem"),
        jwt_public_key_path=str(tmp_path / "pub.pem"),
        access_token_ttl_seconds=-1,  # already expired
    )
    svc = JWTService(settings)
    token, _ = svc.issue_access(
        user_id="00000000-0000-0000-0000-000000000001",
        tenant_id="00000000-0000-0000-0000-000000000002",
        scopes=[],
    )
    with pytest.raises(TokenExpiredError):
        svc.verify_access(token)


def test_jwks_has_one_key(jwt_service: JWTService) -> None:
    jwks = jwt_service.jwks()
    assert "keys" in jwks
    assert len(jwks["keys"]) == 1
    key = jwks["keys"][0]
    assert key["kty"] == "RSA"
    assert key["use"] == "sig"
    assert key["alg"] == "RS256"
    assert "kid" in key and "n" in key and "e" in key
