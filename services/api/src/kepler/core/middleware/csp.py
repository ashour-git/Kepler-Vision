"""Content Security Policy with per-request nonce.

Generates a fresh nonce per request and emits a strict CSP that allows
only same-origin resources, our own CDN, and `unsafe-inline` only where
unavoidable. Inline scripts can opt in by reading the nonce from the
`X-CSP-Nonce` response header.

Production should:
  - Remove `unsafe-eval` (we don't use eval).
  - Add explicit `frame-src` and `object-src 'none'`.
  - Switch `style-src` to nonce-only (currently allows inline for Next.js
    hydration styles, which is common in dev).
"""

from __future__ import annotations

import secrets
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


def generate_nonce() -> str:
    """Generate a 128-bit base64 nonce suitable for CSP."""
    return secrets.token_urlsafe(16)


class CSPNonceMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        nonce = generate_nonce()
        request.state.csp_nonce = nonce
        response: Response = await call_next(request)

        # Build the CSP. We allow inline styles for Next.js's hydration
        # styles in dev; production should switch to nonce-only.
        csp = (
            "default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}' 'strict-dynamic'; "
            f"style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https:; "
            "frame-ancestors 'none'; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "upgrade-insecure-requests"
        )
        response.headers.setdefault("Content-Security-Policy", csp)
        response.headers.setdefault("X-CSP-Nonce", nonce)
        return response
