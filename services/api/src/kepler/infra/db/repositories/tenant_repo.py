"""Tenant repository."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.errors import ConflictError
from ....domain.identity.entities import Tenant, TenantPlan, TenantStatus
from ....domain.identity.value_objects import TenantId
from ..mappers import tenant_to_domain, tenant_to_orm
from ..models import TenantORM


class TenantRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: TenantId | str) -> Optional[Tenant]:
        tid = str(tenant_id)
        stmt = select(TenantORM).where(TenantORM.id == uuid.UUID(tid), TenantORM.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return tenant_to_domain(row) if row else None

    async def get_by_slug(self, slug: str) -> Optional[Tenant]:
        stmt = select(TenantORM).where(TenantORM.slug == slug, TenantORM.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return tenant_to_domain(row) if row else None

    async def add(self, tenant: Tenant) -> None:
        # Uniqueness check (the DB has a unique constraint too, but we want a friendly error)
        existing = await self.get_by_slug(tenant.slug)
        if existing is not None:
            raise ConflictError(
                "Tenant slug already in use",
                details={"field": "slug"},
            )
        self._session.add(tenant_to_orm(tenant))
        await self._session.flush()

    async def update(self, tenant: Tenant) -> None:
        existing = await self._session.get(TenantORM, uuid.UUID(str(tenant.id)))
        if existing is None:
            return
        existing.name = tenant.name
        existing.plan = tenant.plan.value
        existing.status = tenant.status.value
        existing.region = tenant.region
        existing.updated_at = tenant.updated_at
        await self._session.flush()

    async def list_for_user(self, user_id: str) -> list[Tenant]:
        from ..models import MembershipORM

        stmt = (
            select(TenantORM)
            .join(MembershipORM, MembershipORM.tenant_id == TenantORM.id)
            .where(MembershipORM.user_id == uuid.UUID(user_id), TenantORM.deleted_at.is_(None))
            .order_by(TenantORM.created_at)
        )
        result = await self._session.execute(stmt)
        return [tenant_to_domain(row) for row in result.scalars().all()]


__all__ = ["TenantRepository"]
