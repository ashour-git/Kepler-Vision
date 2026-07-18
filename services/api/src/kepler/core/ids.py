"""Identity and identifier utilities."""

from __future__ import annotations

import re
import uuid
from typing import NewType

# ULID-like identifier using UUID4. We use UUID4 because it's well-supported
# in Postgres and Python. A future migration to UUIDv7 (time-ordered) is
# planned — the str representation is identical.
ULID = NewType("ULID", str)
UUID4 = NewType("UUID4", str)

# Public re-export to avoid circular imports
uuid4 = uuid.uuid4

# Allowed characters for slugs
_SLUG_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,62}[a-z0-9])?$")


def new_ulid() -> ULID:
    """Generate a new identifier as a lowercase string."""
    return ULID(str(uuid4()))


def parse_ulid(value: str) -> ULID:
    """Parse a string into a ULID or raise ValueError."""
    try:
        # Validates UUID format
        uuid.UUID(value)
    except (ValueError, AttributeError, TypeError) as exc:
        raise ValueError(f"Invalid identifier: {value!r}") from exc
    return ULID(str(value).lower())


def is_valid_slug(value: str) -> bool:
    """Return True if `value` is a valid URL/DB slug."""
    if not value or len(value) > 64:
        return False
    return bool(_SLUG_PATTERN.match(value))


def normalize_email(email: str) -> str:
    """Lowercase and strip the local part domain of an email address."""
    return email.strip().lower()
