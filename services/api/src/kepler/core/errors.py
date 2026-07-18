"""Application error hierarchy.

All domain and infrastructure errors inherit from AppError. The API layer
maps these to the public error envelope; nothing else leaks to the client.
"""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base for all application errors."""

    http_status: int = 500
    code: str = "internal_error"
    retryable: bool = False

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details: dict[str, Any] = details or {}
        self.cause = cause

    def to_envelope(self, request_id: str | None = None) -> dict[str, Any]:
        """Convert to the public error envelope."""
        envelope: dict[str, Any] = {
            "code": self.code,
            "message": self.message,
            "request_id": request_id,
            "retryable": self.retryable,
        }
        if self.details:
            envelope["details"] = self.details
        return envelope


class ValidationError(AppError):
    http_status = 400
    code = "validation_failed"
    retryable = False


class AuthenticationError(AppError):
    http_status = 401
    code = "unauthenticated"
    retryable = False


class InvalidCredentialsError(AuthenticationError):
    code = "invalid_credentials"


class InvalidTokenError(AuthenticationError):
    code = "invalid_token"


class TokenExpiredError(AuthenticationError):
    code = "token_expired"


class TokenReuseError(AuthenticationError):
    """Refresh token was reused â€” entire family revoked."""

    code = "token_reuse_detected"


class PermissionError_(AppError):
    http_status = 403
    code = "permission_denied"
    retryable = False


class NotFoundError(AppError):
    http_status = 404
    code = "not_found"
    retryable = False


class ConflictError(AppError):
    http_status = 409
    code = "conflict"
    retryable = False


class ConcurrentModificationError(ConflictError):
    code = "concurrent_modification"


class InvalidStateTransitionError(ConflictError):
    code = "invalid_state_transition"


class EmailAlreadyExistsError(ConflictError):
    code = "email_already_exists"


class TenantSlugTakenError(ConflictError):
    code = "tenant_slug_taken"


class RateLimitedError(AppError):
    http_status = 429
    code = "rate_limited"
    retryable = True

    def __init__(
        self,
        message: str = "Too many requests",
        *,
        retry_after_seconds: int = 60,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, details=details)
        self.retry_after_seconds = retry_after_seconds


class AccountLockedError(AuthenticationError):
    code = "account_locked"


class AccountDisabledError(AuthenticationError):
    code = "account_disabled"


class DependencyError(AppError):
    http_status = 503
    code = "dependency_unavailable"
    retryable = True


class InternalError(AppError):
    """An unexpected error. Never includes internals in the message."""

    http_status = 500
    code = "internal"
    retryable = False

