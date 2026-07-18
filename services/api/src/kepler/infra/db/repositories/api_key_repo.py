"""API key repository."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....domain.identity.entities import ApiKey, ApiKeyStatus
from ....domain.identity.value_objects import ApiKeyId, UserId
from ..mappers import api_key_to_domain, api_key_to_orm
from ..models import ApiKeyORM


class ApiKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, api_key_id: ApiKeyId | str) -> Optional[ApiKey]:
        stmt = select(ApiKeyORM).where(ApiKeyORM.id == uuid.UUID(str(api_key_id)))
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return api_key_to_domain(row) if row else None

    async def list_for_user(self, user_id: UserId | str) -> list[ApiKey]:
        stmt = (
            select(ApiKeyORM)
            .where(ApiKeyORM.user_id == uuid.UUID(str(user_id)))
            .order_by(ApiKeyORM.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [api_key_to_domain(row) for row in result.scalars().all()]

    async def add(self, api_key: ApiKey) -> None:
        self._session.add(api_key_to_orm(api_key))
        await self._session.flush()

    async def revoke(self, api_key_id: ApiKeyId | str) -> Optional[ApiKey]:
        from ....core.time import utc_now

        existing = await self._session.get(ApiKeyORM, uuid.UUID(str(api_key_id)))
        if existing is None:
            return None
        existing.status = ApiKeyStatus.REVOKED.value
        existing.revoked_at = utc_now()
        existing.updated_at = utc_now()
        await self._session.flush()
        return api_key_to_domain(existing)


__all__ = ["ApiKeyRepository"]
