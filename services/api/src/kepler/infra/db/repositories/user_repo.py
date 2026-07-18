"""User repository."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ....core.errors import ConflictError
from ....domain.identity.entities import User, UserStatus
from ....domain.identity.value_objects import Email, UserId
from ..mappers import user_to_domain, user_to_orm
from ..models import UserORM


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, user_id: UserId | str) -> Optional[User]:
        uid = str(user_id)
        stmt = select(UserORM).where(UserORM.id == uuid.UUID(uid), UserORM.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return user_to_domain(row) if row else None

    async def get_by_email(self, email: str | Email) -> Optional[User]:
        e = email.value if isinstance(email, Email) else email
        stmt = select(UserORM).where(UserORM.email == e, UserORM.deleted_at.is_(None))
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return user_to_domain(row) if row else None

    async def add(self, user: User) -> None:
        # Uniqueness check; the DB enforces it too.
        existing = await self.get_by_email(user.email)
        if existing is not None:
            raise ConflictError(
                "Email already registered",
                details={"field": "email"},
            )
        self._session.add(user_to_orm(user))
        await self._session.flush()

    async def update(self, user: User) -> None:
        existing = await self._session.get(UserORM, uuid.UUID(str(user.id)))
        if existing is None:
            return
        existing.full_name = user.full_name
        existing.avatar_url = user.avatar_url
        existing.locale = user.locale
        existing.timezone = user.timezone
        existing.mfa_enabled = user.mfa_enabled
        existing.mfa_secret_enc = user.mfa_secret_enc
        existing.status = user.status.value
        existing.last_sign_in_at = user.last_sign_in_at
        existing.updated_at = user.updated_at
        existing.password_hash = user.password_hash
        await self._session.flush()

    async def record_sign_in(self, user_id: UserId | str) -> None:
        uid = str(user_id)
        row = await self._session.get(UserORM, uuid.UUID(uid))
        if row is not None:
            from ....core.time import utc_now

            row.last_sign_in_at = utc_now()
            await self._session.flush()


__all__ = ["UserRepository"]
