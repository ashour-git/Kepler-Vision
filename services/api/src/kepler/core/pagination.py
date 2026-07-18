"""Cursor-based pagination utilities.

Cursor format: opaque base64url(JSON({k: v, d: 'desc|asc'})). For our use
case we keep it simple: cursor is just the last seen ID, since our tables
are always sorted by a tie-breaker of `id`.

Use `encode_cursor(last_id)` and `decode_cursor(cursor)` for clients and
repositories respectively.
"""

from __future__ import annotations

import base64
import binascii
from typing import Final

from .errors import ValidationError
from .ids import ULID, parse_ulid

MAX_LIMIT: Final[int] = 200
DEFAULT_LIMIT: Final[int] = 50


def encode_cursor(last_id: str) -> str:
    """Encode a last-seen identifier as an opaque cursor."""
    if not last_id:
        raise ValidationError("Cannot encode empty cursor")
    raw = last_id.encode("utf-8")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def decode_cursor(cursor: str | None) -> ULID | None:
    """Decode an opaque cursor to an identifier or None."""
    if cursor is None or cursor == "":
        return None
    try:
        # Re-add padding
        padding = "=" * (-len(cursor) % 4)
        raw = base64.urlsafe_b64decode(cursor + padding)
        value = raw.decode("utf-8")
        return parse_ulid(value)
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise ValidationError(
            "Invalid cursor",
            details={"cursor": "malformed"},
        ) from exc


def clamp_limit(limit: int) -> int:
    """Clamp a limit to the allowed range."""
    if limit < 1:
        return 1
    if limit > MAX_LIMIT:
        return MAX_LIMIT
    return limit
