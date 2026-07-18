"""Refresh token repository.

Persistence of refresh token JTIs and their family state. The actual
revocation check also consults the Redis store for fast path; this table
is the source of truth.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.ids import new_ulid
from ....core.time import utc_now
from ..models import RefreshTokenORM


class RefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(
        self,
        *,
        user_id: str,
        family_id: str,
        jti: str,
        user_agent: Optional[str],
        ip_prefix: Optional[str],
        expires_at: datetime,
    ) -> str:
        record_id = new_ulid()
        row = RefreshTokenORM(
            id=uuid.UUID(record_id),
            user_id=uuid.UUID(user_id),
            family_id=uuid.UUID(family_id),
            jti=jti,
            user_agent=user_agent,
            ip_prefix=ip_prefix,
            expires_at=expires_at,
        )
        self._session.add(row)
        await self._session.flush()
        return record_id

    async def get_by_jti(self, jti: str) -> Optional[RefreshTokenORM]:
        stmt = select(RefreshTokenORM).where(RefreshTokenORM.jti == jti)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def mark_used(self, jti: str) -> None:
        stmt = update(RefreshTokenORM).where(RefreshTokenORM.jti == jti).values(used_at=utc_now())
        await self._session.execute(stmt)

    async def revoke_jti(self, jti: str) -> None:
        stmt = (
            update(RefreshTokenORM)
            .where(RefreshTokenORM.jti == jti)
            .values(revoked_at=utc_now(), updated_at=utc_now())
        )
        await self._session.execute(stmt)

    async def revoke_family(self, family_id: str) -> int:
        stmt = (
            update(RefreshTokenORM)
            .where(RefreshTokenORM.family_id == uuid.UUID(family_id), RefreshTokenORM.revoked_at.is_(None))
            .values(
                revoked_at=utc_now(),
                family_revoked_at=utc_now(),
                updated_at=utc_now(),
            )
        )
        result = await self._session.execute(stmt)
        return int(result.rowcount or 0)

    async def family_revoked(self, family_id: str) -> bool:
        stmt = select(RefreshTokenORM.family_revoked_at).where(
            RefreshTokenORM.family_id == uuid.UUID(family_id),
            RefreshTokenORM.family_revoked_at.is_not(None),
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None


__all__ = ["RefreshTokenRepository"]
