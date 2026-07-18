"""Membership repository."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.ids import new_ulid
from ....domain.identity.entities import Membership
from ....domain.identity.value_objects import TenantId, UserId
from ..mappers import membership_to_domain, membership_to_orm
from ..models import MembershipORM


class MembershipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UserId | str, tenant_id: TenantId | str) -> Optional[Membership]:
        stmt = select(MembershipORM).where(
            MembershipORM.user_id == uuid.UUID(str(user_id)),
            MembershipORM.tenant_id == uuid.UUID(str(tenant_id)),
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return membership_to_domain(row) if row else None

    async def get_by_tenant_and_user(self, tenant_id: TenantId | str, user_id: UserId | str) -> Optional[Membership]:
        return await self.get(user_id, tenant_id)

    async def list_for_tenant(self, tenant_id: TenantId | str) -> list[Membership]:
        stmt = (
            select(MembershipORM)
            .where(MembershipORM.tenant_id == uuid.UUID(str(tenant_id)))
            .order_by(MembershipORM.created_at)
        )
        result = await self._session.execute(stmt)
        return [membership_to_domain(row) for row in result.scalars().all()]

    async def list_for_user(self, user_id: UserId | str) -> list[Membership]:
        stmt = select(MembershipORM).where(MembershipORM.user_id == uuid.UUID(str(user_id)))
        result = await self._session.execute(stmt)
        return [membership_to_domain(row) for row in result.scalars().all()]

    async def add(
        self,
        *,
        user_id: UserId,
        tenant_id: TenantId,
        role: str,
        invited_by: Optional[UserId] = None,
    ) -> Membership:
        membership = Membership(
            id=new_ulid(),
            user_id=user_id,
            tenant_id=tenant_id,
            role=role,
            invited_by=invited_by,
        )
        self._session.add(membership_to_orm(membership))
        await self._session.flush()
        return membership

    async def update_role(self, *, user_id: UserId, tenant_id: TenantId, role: str) -> Optional[Membership]:
        existing = await self.get(user_id, tenant_id)
        if existing is None:
            return None
        # Get the ORM row directly for update
        stmt = select(MembershipORM).where(
            MembershipORM.user_id == uuid.UUID(str(user_id)),
            MembershipORM.tenant_id == uuid.UUID(str(tenant_id)),
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.role = role
        from ....core.time import utc_now

        row.updated_at = utc_now()
        await self._session.flush()
        return membership_to_domain(row)

    async def remove(self, *, user_id: UserId, tenant_id: TenantId) -> bool:
        stmt = select(MembershipORM).where(
            MembershipORM.user_id == uuid.UUID(str(user_id)),
            MembershipORM.tenant_id == uuid.UUID(str(tenant_id)),
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self._session.delete(row)
        await self._session.flush()
        return True


__all__ = ["MembershipRepository"]
