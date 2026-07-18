"""Argon2id password hashing.

We use argon2id with sensible defaults for an interactive API:
- time_cost=2 (≈50-100ms on modern CPUs)
- memory_cost=64 MiB
- parallelism=1

`hash_password` returns a self-describing PHC string; `verify_password` is
constant-time and re-hashes on parameter upgrade.
"""

from __future__ import annotations

from argon2 import PasswordHasher
from argon2.exceptions import (
    InvalidHashError,
    VerifyMismatchError,
    VerificationError,
)

from ..errors import InternalError

_hasher = PasswordHasher(
    time_cost=2,
    memory_cost=64 * 1024,  # 64 MiB
    parallelism=1,
    hash_len=32,
    salt_len=16,
)


def hash_password(plaintext: str) -> str:
    """Hash a plaintext password using argon2id. Returns a PHC string."""
    if not plaintext:
        raise ValueError("Password must not be empty")
    try:
        return _hasher.hash(plaintext)
    except Exception as exc:  # pragma: no cover - argon2id should not fail
        raise InternalError("Password hashing failed", cause=exc) from exc


def verify_password(plaintext: str, hashed: str) -> bool:
    """Verify a plaintext password against an argon2id hash.

    Returns True on match, False otherwise. Never raises on bad input.
    """
    if not plaintext or not hashed:
        return False
    try:
        _hasher.verify(hashed, plaintext)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    """Return True if the hash was made with weaker parameters."""
    try:
        return _hasher.check_needs_rehash(hashed)
    except InvalidHashError:
        return True
