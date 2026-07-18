"""Refresh token store.

We use Redis as the fast path for refresh-token checks:

- `refresh:lock:{jti}` — short-TTL lock set on rotate; prevents two concurrent
  rotates from both succeeding.
- `refresh:revoked:{jti}` — denylist, TTL = remaining token lifetime.
- `login:fail:{email}` — counter for login throttling.
- `login:lock:{email}` — lockout marker, TTL = lockout window.

The Postgres `refresh_tokens` table remains the source of truth; the cache
is purely a fast lookup for hot path checks.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

from redis.asyncio import Redis

from ...settings import get_settings


@dataclass(frozen=True, slots=True)
class LockResult:
    """Result of a refresh-token rotate attempt."""

    acquired: bool
    already_used: bool


class RefreshTokenStore:
    def __init__(self, client: Redis) -> None:
        self._client = client
        self._settings = get_settings()

    # ---------------------------------------------------------------- keys

    @staticmethod
    def _lock_key(jti: str) -> str:
        return f"refresh:lock:{jti}"

    @staticmethod
    def _revoked_key(jti: str) -> str:
        return f"refresh:revoked:{jti}"

    @staticmethod
    def _fail_key(email: str) -> str:
        digest = hashlib.sha256(email.lower().encode("utf-8")).hexdigest()[:32]
        return f"login:fail:{digest}"

    @staticmethod
    def _lockout_key(email: str) -> str:
        digest = hashlib.sha256(email.lower().encode("utf-8")).hexdigest()[:32]
        return f"login:lock:{digest}"

    # ----------------------------------------------------- refresh rotation

    async def try_lock_for_rotation(self, jti: str, ttl_seconds: int) -> LockResult:
        """Try to acquire a rotation lock for `jti`.

        Returns `LockResult(acquired=True, ...)` if this is the first rotate,
        or `acquired=False` if another request already rotated (or revoked)
        this token. If the token is already on the denylist, `already_used=True`.
        """
        lock_key = self._lock_key(jti)
        revoked_key = self._revoked_key(jti)

        # If the token is revoked, treat as already used.
        if await self._client.exists(revoked_key):
            return LockResult(acquired=False, already_used=True)

        # SET NX with TTL — atomic.
        acquired_raw = await self._client.set(lock_key, "1", nx=True, ex=ttl_seconds)
        acquired = bool(acquired_raw)
        if not acquired:
            # Someone else is rotating; treat as a reuse.
            return LockResult(acquired=False, already_used=False)
        return LockResult(acquired=True, already_used=False)

    async def commit_rotation(self, jti: str, ttl_seconds: int) -> None:
        """After a successful DB update, move the lock into the denylist."""
        await self._client.set(self._revoked_key(jti), "1", ex=ttl_seconds)
        await self._client.delete(self._lock_key(jti))

    async def release_rotation_lock(self, jti: str) -> None:
        """Release a lock without committing the rotation (e.g. on DB error)."""
        await self._client.delete(self._lock_key(jti))

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        """Add a token to the denylist."""
        await self._client.set(self._revoked_key(jti), "1", ex=ttl_seconds)

    # ----------------------------------------------------- login throttling

    async def record_failed_login(self, email: str) -> int:
        """Increment the failure counter; return the new value."""
        key = self._fail_key(email)
        pipe = self._client.pipeline()
        pipe.incr(key)
        pipe.expire(key, self._settings.rate_limit_login_window_seconds)
        results = await pipe.execute()
        return int(results[0])

    async def clear_failed_logins(self, email: str) -> None:
        await self._client.delete(self._fail_key(email))

    async def is_locked_out(self, email: str) -> Optional[int]:
        """Return remaining lockout seconds if locked, else None."""
        key = self._lockout_key(email)
        ttl = await self._client.ttl(key)
        if ttl is None or ttl < 0:
            return None
        return int(ttl)

    async def set_lockout(self, email: str) -> None:
        key = self._lockout_key(email)
        await self._client.set(
            key,
            "1",
            ex=self._settings.rate_limit_login_lockout_seconds,
        )


_singleton: Optional[RefreshTokenStore] = None


def get_refresh_token_store() -> RefreshTokenStore:
    """Return the process-wide store."""
    global _singleton
    if _singleton is None:
        from .redis import get_redis_client

        _singleton = RefreshTokenStore(get_redis_client())
    return _singleton


def reset_refresh_token_store() -> None:
    """Drop the singleton (used in tests)."""
    global _singleton
    _singleton = None
