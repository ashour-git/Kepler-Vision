"""Rate-limit headers.

Emits `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset`
on responses for endpoints that enforce limits. The headers follow the
de-facto standard used by GitHub, Twitter, and others.
"""

from __future__ import annotations

from fastapi import Response

DEFAULT_LIMIT = 60  # requests per minute, for general API endpoints


def apply_rate_limit_headers(
    response: Response,
    *,
    limit: int,
    remaining: int,
    reset_seconds: int,
) -> None:
    """Attach rate-limit headers to a response."""
    response.headers["X-RateLimit-Limit"] = str(limit)
    response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
    response.headers["X-RateLimit-Reset"] = str(max(0, reset_seconds))


def login_rate_limit_headers(*, remaining: int) -> dict[str, str]:
    """Headers for the sign-in endpoint (limit from settings)."""
    from ...settings import get_settings

    settings = get_settings()
    return {
        "X-RateLimit-Limit": str(settings.rate_limit_login_per_email),
        "X-RateLimit-Remaining": str(max(0, remaining)),
        "X-RateLimit-Reset": str(settings.rate_limit_login_window_seconds),
    }


__all__ = [
    "apply_rate_limit_headers",
    "login_rate_limit_headers",
    "DEFAULT_LIMIT",
]
