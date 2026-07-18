"""Time utilities.

We always work in UTC. Application code should not import datetime directly;
it should use `utc_now()` so tests can freeze the clock.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return current UTC time as a timezone-aware datetime."""
    return datetime.now(UTC)
