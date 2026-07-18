"""Domain services for identity.

These are stateless functions/classes that orchestrate domain logic that
doesn't belong to a single entity. They do not perform I/O.
"""

from __future__ import annotations

import re
from typing import Any

from ...core.errors import ValidationError

# Tenant slug: lowercase, digits, dashes; 3-32 chars; no leading/trailing dash.
_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{1,30}[a-z0-9])?$")


def is_valid_tenant_slug(slug: str) -> bool:
    """Return True if `slug` is a valid tenant slug."""
    return bool(slug) and bool(_SLUG_RE.match(slug))


def check_password_policy(password: str) -> None:
    """Raise ValidationError if `password` does not meet the policy.

    Policy: ≥12 characters, no whitespace-only, no all-same-character.
    """
    if not isinstance(password, str):
        raise ValidationError("Password must be a string", details={"field": "password"})
    if len(password) < 12:
        raise ValidationError(
            "Password must be at least 12 characters",
            details={"field": "password", "min_length": 12},
        )
    if len(password) > 1024:
        raise ValidationError(
            "Password is too long",
            details={"field": "password", "max_length": 1024},
        )
    if password.strip() == "":
        raise ValidationError("Password must not be whitespace", details={"field": "password"})
    if len(set(password)) < 4:
        raise ValidationError(
            "Password is too simple",
            details={"field": "password", "reason": "low_entropy"},
        )


def password_meets_policy(password: str) -> bool:
    """Boolean wrapper around `check_password_policy`."""
    try:
        check_password_policy(password)
        return True
    except ValidationError:
        return False


def compute_audit_payload(before: dict[str, Any] | None, after: dict[str, Any] | None) -> dict[str, Any]:
    """Compute a compact audit payload. We never store secrets in `after`."""
    safe_after: dict[str, Any] | None = None
    if after is not None:
        safe_after = {k: v for k, v in after.items() if k not in {"password", "password_hash", "token"}}
    safe_before: dict[str, Any] | None = None
    if before is not None:
        safe_before = {k: v for k, v in before.items() if k not in {"password", "password_hash", "token"}}
    return {"before": safe_before, "after": safe_after}
