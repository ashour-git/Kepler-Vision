"""Audit log repository.

The history table is append-only. The repository exposes a single
`append` method; updates and deletes raise.
"""

from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.identity.value_objects import TenantId, UserId
from ..models import AuditLogORM


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def append(
        self,
        *,
        tenant_id: TenantId | str,
        actor_id: Optional[UserId | str],
        actor_type: str,
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        project_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        ip: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_id: Optional[str] = None,
    ) -> None:
        row = AuditLogORM(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(str(tenant_id)),
            actor_id=uuid.UUID(str(actor_id)) if actor_id else None,
            actor_type=actor_type,
            action=action,
            resource_type=resource_type,
            resource_id=uuid.UUID(resource_id) if resource_id else None,
            project_id=uuid.UUID(project_id) if project_id else None,
            metadata_=metadata or {},
            ip=ip,
            user_agent=user_agent,
            request_id=uuid.UUID(request_id) if request_id else None,
        )
        self._session.add(row)
        await self._session.flush()


__all__ = ["AuditLogRepository"]
