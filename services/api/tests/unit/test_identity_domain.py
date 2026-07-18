"""Unit tests for the identity domain services."""

from __future__ import annotations

import pytest

from kepler.core.errors import ValidationError
from kepler.domain.identity.services import (
    check_password_policy,
    compute_audit_payload,
    is_valid_tenant_slug,
    password_meets_policy,
)


def test_is_valid_tenant_slug_accepts_good_values() -> None:
    assert is_valid_tenant_slug("acme")
    assert is_valid_tenant_slug("acme-corp")
    assert is_valid_tenant_slug("a1b2c3")


def test_is_valid_tenant_slug_rejects_bad_values() -> None:
    assert not is_valid_tenant_slug("")
    assert not is_valid_tenant_slug("-leading")
    assert not is_valid_tenant_slug("trailing-")
    assert not is_valid_tenant_slug("with space")
    assert not is_valid_tenant_slug("UPPER")
    assert not is_valid_tenant_slug("a" * 100)


def test_password_policy_enforces_min_length() -> None:
    with pytest.raises(ValidationError):
        check_password_policy("short")
    assert password_meets_policy("this-is-a-very-long-password-1234")


def test_password_policy_rejects_low_entropy() -> None:
    with pytest.raises(ValidationError):
        check_password_policy("aaaaaaaaaaaa")


def test_password_policy_rejects_whitespace() -> None:
    with pytest.raises(ValidationError):
        check_password_policy("            ")


def test_audit_payload_redacts_sensitive_keys() -> None:
    after = {
        "name": "Maya",
        "password": "should-not-appear",
        "password_hash": "$argon2id$...",
        "token": "eyJhbGciOi...",
    }
    payload = compute_audit_payload(None, after)
    assert "password" not in payload["after"]
    assert "password_hash" not in payload["after"]
    assert "token" not in payload["after"]
    assert payload["after"]["name"] == "Maya"
