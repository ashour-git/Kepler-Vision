"""Identity domain events.

Domain events are emitted by the application layer and routed to listeners
(via the outbox, in a later sprint). Each event is a frozen dataclass
with a stable `type` string.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from ...core.time import utc_now
from .value_objects import TenantId, UserId


def _new_event_id() -> str:
    return str(uuid4())


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """Base class for all domain events."""

    event_id: str = field(default_factory=_new_event_id)
    occurred_at: datetime = field(default_factory=utc_now)
    tenant_id: Optional[TenantId] = None
    actor_id: Optional[UserId] = None

    @property
    def type(self) -> str:  # pragma: no cover - overridden in subclasses
        return "domain.event"

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "type": self.type,
            "occurred_at": self.occurred_at.isoformat(),
            "tenant_id": str(self.tenant_id) if self.tenant_id else None,
            "actor_id": str(self.actor_id) if self.actor_id else None,
        }


@dataclass(frozen=True, slots=True)
class UserSignedUp(DomainEvent):
    user_id: UserId = field(default_factory=lambda: UserId("00000000-0000-0000-0000-000000000000"))

    @property
    def type(self) -> str:
        return "identity.user.signed_up"


@dataclass(frozen=True, slots=True)
class UserSignedIn(DomainEvent):
    user_id: UserId = field(default_factory=lambda: UserId("00000000-0000-0000-0000-000000000000"))

    @property
    def type(self) -> str:
        return "identity.user.signed_in"


@dataclass(frozen=True, slots=True)
class UserSignedOut(DomainEvent):
    user_id: UserId = field(default_factory=lambda: UserId("00000000-0000-0000-0000-000000000000"))

    @property
    def type(self) -> str:
        return "identity.user.signed_out"


@dataclass(frozen=True, slots=True)
class TokenRefreshed(DomainEvent):
    user_id: UserId = field(default_factory=lambda: UserId("00000000-0000-0000-0000-000000000000"))
    family_id: str = ""

    @property
    def type(self) -> str:
        return "identity.token.refreshed"


@dataclass(frozen=True, slots=True)
class TokenRevoked(DomainEvent):
    """Emitted when a refresh family is revoked (logout, theft detection, etc.)."""

    user_id: UserId = field(default_factory=lambda: UserId("00000000-0000-0000-0000-000000000000"))
    family_id: str = ""
    reason: str = "user_signout"

    @property
    def type(self) -> str:
        return "identity.token.revoked"


@dataclass(frozen=True, slots=True)
class MembershipAdded(DomainEvent):
    user_id: UserId = field(default_factory=lambda: UserId("00000000-0000-0000-0000-000000000000"))
    role: str = "member"

    @property
    def type(self) -> str:
        return "identity.membership.added"


@dataclass(frozen=True, slots=True)
class MembershipRemoved(DomainEvent):
    user_id: UserId = field(default_factory=lambda: UserId("00000000-0000-0000-0000-000000000000"))

    @property
    def type(self) -> str:
        return "identity.membership.removed"


@dataclass(frozen=True, slots=True)
class MembershipRoleChanged(DomainEvent):
    user_id: UserId = field(default_factory=lambda: UserId("00000000-0000-0000-0000-000000000000"))
    old_role: str = ""
    new_role: str = ""

    @property
    def type(self) -> str:
        return "identity.membership.role_changed"
