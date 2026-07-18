"""Async Redis client wrapper.

The client is process-wide. Tests can reset it.
"""

from __future__ import annotations

from typing import Optional

import redis.asyncio as redis

from ...settings import Settings, get_settings

_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """Return the process-wide Redis client, creating it on first use."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = redis.from_url(
            settings.redis_url,
            max_connections=settings.redis_max_connections,
            decode_responses=True,
        )
    return _client


def reset_redis_client() -> None:
    """Drop the cached client. Used in tests."""
    global _client
    _client = None


RedisClient = redis.Redis
