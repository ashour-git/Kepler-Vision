"""Request ID middleware.

Reads `X-Request-Id` from the incoming request (or generates a new ULID),
binds it to the logging context, and echoes it back in the response.
"""

from __future__ import annotations

import time
import uuid
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from ..ids import new_ulid
from ..logging import request_id_var


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        incoming = request.headers.get("x-request-id")
        try:
            uuid.UUID(incoming) if incoming else None
            request_id = incoming or new_ulid()
        except (ValueError, TypeError):
            request_id = new_ulid()

        token = request_id_var.set(request_id)
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        finally:
            request_id_var.reset(token)
        response.headers["X-Request-Id"] = request_id
        return response
