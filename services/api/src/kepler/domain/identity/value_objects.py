"""Identity value objects.

These are validated, immutable wrappers around primitive types. They are
the boundary between untrusted input and the domain layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from email_validator import EmailNotValidError, validate_email

from ...core.errors import ValidationError
from ...core.ids import ULID, parse_ulid


@dataclass(frozen=True, slots=True)
class UserId:
    """A strongly-typed user identifier."""

    value: str

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "value", str(parse_ulid(self.value)))
        except ValueError as exc:
            raise ValidationError("Invalid user id", details={"field": "user_id"}) from exc

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class TenantId:
    """A strongly-typed tenant identifier."""

    value: str

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "value", str(parse_ulid(self.value)))
        except ValueError as exc:
            raise ValidationError("Invalid tenant id", details={"field": "tenant_id"}) from exc

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class ApiKeyId:
    """A strongly-typed API key identifier."""

    value: str

    def __post_init__(self) -> None:
        try:
            object.__setattr__(self, "value", str(parse_ulid(self.value)))
        except ValueError as exc:
            raise ValidationError("Invalid api key id", details={"field": "api_key_id"}) from exc

    def __str__(self) -> str:
        return self.value


# Conservative email regex pre-check (full validation done by email-validator)
_EMAIL_BASIC = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@dataclass(frozen=True, slots=True)
class Email:
    """A validated email address. Stored lowercased."""

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise ValidationError("Email must be a string", details={"field": "email"})
        normalized = self.value.strip().lower()
        if not normalized or len(normalized) > 254:
            raise ValidationError("Email length out of range", details={"field": "email"})
        if not _EMAIL_BASIC.match(normalized):
            raise ValidationError("Email format invalid", details={"field": "email"})
        try:
            validate_email(normalized, check_deliverability=False)
        except EmailNotValidError as exc:
            raise ValidationError("Email is not valid", details={"field": "email"}) from exc
        object.__setattr__(self, "value", normalized)

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True, slots=True)
class Password:
    """A plaintext password candidate. Validated against policy.

    Used only at the application boundary; the domain never stores plaintext.
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise ValidationError("Password must be a string", details={"field": "password"})
        if len(self.value) < 12:
            raise ValidationError(
                "Password must be at least 12 characters",
                details={"field": "password", "min_length": 12},
            )
        if len(self.value) > 1024:
            raise ValidationError("Password too long", details={"field": "password", "max_length": 1024})

    def __str__(self) -> str:  # pragma: no cover - sensitive
        return "<redacted>"
