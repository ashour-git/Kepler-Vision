"""Security headers middleware.

Adds a baseline of protective headers to every response:
  - Strict-Transport-Security (HSTS) for HTTPS-only enforcement
  - X-Content-Type-Options: nosniff
  - X-Frame-Options: DENY
  - Referrer-Policy: strict-origin-when-cross-origin
  - Permissions-Policy: restrictive defaults
  - Cross-Origin-Opener-Policy: same-origin

For the HTML docs and the web app, CSP nonces are emitted by a separate
middleware (P1.18). This middleware is API-focused.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

_DEFAULT_HEADERS: dict[str, str] = {
    # P1.17: HSTS — 2 years, include subdomains, preload-eligible.
    # Production should confirm domain is on the HSTS preload list.
    "Strict-Transport-Security": "max-age=63072000; includeSubDomains; preload",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": (
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
        "magnetometer=(), microphone=(), payment=(), usb=(), "
        "interest-cohort=()"
    ),
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-site",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response: Response = await call_next(request)
        for key, value in _DEFAULT_HEADERS.items():
            response.headers.setdefault(key, value)
        return response
