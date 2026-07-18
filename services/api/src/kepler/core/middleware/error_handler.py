"""Global error handler middleware.

Catches AppError and unknown exceptions, returns the standard envelope.
"""

from __future__ import annotations

from typing import Awaitable, Callable

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError
from starlette.middleware.base import BaseHTTPMiddleware

from ...domain.identity.services import compute_audit_payload
from ..errors import (
    AppError,
    InternalError,
    RateLimitedError,
    ValidationError,
)
from ..logging import get_logger, request_id_var

_log = get_logger("kepler.error")


def _envelope(
    *,
    code: str,
    message: str,
    request_id: str | None,
    retryable: bool,
    status: int,
    details: dict | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body: dict[str, object] = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
            "retryable": retryable,
        }
    }
    if details:
        body["error"]["details"] = details
    response = JSONResponse(status_code=status, content=body)
    if request_id:
        response.headers["X-Request-Id"] = request_id
    if headers:
        for k, v in headers.items():
            response.headers[k] = v
    return response


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable],
    ) -> JSONResponse:
        try:
            response = await call_next(request)
            return response  # type: ignore[return-value]
        except RateLimitedError as exc:
            return _envelope(
                code=exc.code,
                message=exc.message,
                request_id=request_id_var.get(),
                retryable=exc.retryable,
                status=exc.http_status,
                details=exc.details or {"retry_after_seconds": exc.retry_after_seconds},
                headers={"Retry-After": str(exc.retry_after_seconds)},
            )
        except ValidationError as exc:
            return _envelope(
                code=exc.code,
                message=exc.message,
                request_id=request_id_var.get(),
                retryable=exc.retryable,
                status=exc.http_status,
                details=exc.details,
            )
        except AppError as exc:
            return _envelope(
                code=exc.code,
                message=exc.message,
                request_id=request_id_var.get(),
                retryable=exc.retryable,
                status=exc.http_status,
                details=exc.details,
            )
        except PydanticValidationError as exc:
            fields: dict[str, list[str]] = {}
            for err in exc.errors():
                loc = ".".join(str(p) for p in err.get("loc", [])) or "_"
                fields.setdefault(loc, []).append(err.get("msg", "invalid"))
            return _envelope(
                code="validation_failed",
                message="Request validation failed",
                request_id=request_id_var.get(),
                retryable=False,
                status=400,
                details={"fields": fields},
            )
        except Exception as exc:  # noqa: BLE001 - last-resort handler
            _log.exception("unhandled_error", error=str(exc), path=str(request.url))
            return _envelope(
                code="internal",
                message="An unexpected error occurred",
                request_id=request_id_var.get(),
                retryable=False,
                status=500,
            )


__all__ = ["ErrorHandlerMiddleware", "compute_audit_payload", "InternalError"]
