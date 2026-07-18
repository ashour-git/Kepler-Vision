"""Unit tests for the password hashing service."""

from __future__ import annotations

import pytest

from kepler.core.security.password import hash_password, needs_rehash, verify_password


def test_hash_returns_phc_string(strong_password: str) -> None:
    h = hash_password(strong_password)
    assert h.startswith("$argon2id$")
    assert verify_password(strong_password, h) is True


def test_verify_rejects_wrong_password(strong_password: str) -> None:
    h = hash_password(strong_password)
    assert verify_password("wrong-password-1234", h) is False


def test_verify_handles_empty_inputs() -> None:
    assert verify_password("", "$argon2id$invalid") is False
    assert verify_password("anything", "") is False


def test_hash_password_rejects_empty() -> None:
    with pytest.raises(ValueError):
        hash_password("")


def test_needs_rehash_returns_bool(strong_password: str) -> None:
    h = hash_password(strong_password)
    assert isinstance(needs_rehash(h), bool)
