"""API key endpoints."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field

from ...application.identity.commands import (
    CreateApiKeyCommand,
    CreateApiKeyResult,
    RevokeApiKeyCommand,
    create_api_key,
    revoke_api_key,
)
from ...application.identity.queries import ListApiKeysQuery, list_api_keys
from ..deps import (
    ActorPermissionsDep,
    CurrentUserIdDep,
    UnitOfWorkDep,
)

router = APIRouter(prefix="/users/me/api-keys", tags=["api-keys"])


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class _ApiKeyOut(BaseModel):
    id: str
    name: str
    key_prefix: str
    scopes: list[str]
    status: str
    last_used_at: Optional[str]
    expires_at: Optional[str]
    created_at: str


class CreateApiKeyIn(_StrictModel):
    name: str = Field(min_length=1, max_length=120)
    scopes: list[str] = Field(default_factory=list, max_length=50)
    expires_at: Optional[str] = None  # ISO 8601


class CreateApiKeyOut(BaseModel):
    api_key: _ApiKeyOut
    plaintext: str  # shown only on create


@router.get("", response_model=list[_ApiKeyOut], summary="List API keys")
async def list_api_keys_endpoint(
    uow: UnitOfWorkDep,
    actor_permissions: ActorPermissionsDep,
    user_id: CurrentUserIdDep,
) -> list[_ApiKeyOut]:
    keys = await list_api_keys(
        ListApiKeysQuery(user_id=user_id, actor_permissions=actor_permissions),
        uow=uow,
    )
    return [_ApiKeyOut(**k.to_dict()) for k in keys]


@router.post(
    "",
    response_model=CreateApiKeyOut,
    status_code=status.HTTP_201_CREATED,
    summary="Create API key",
)
async def create_api_key_endpoint(
    payload: CreateApiKeyIn,
    uow: UnitOfWorkDep,
    actor_permissions: ActorPermissionsDep,
    user_id: CurrentUserIdDep,
) -> CreateApiKeyOut:
    cmd = CreateApiKeyCommand(
        user_id=user_id,
        name=payload.name,
        scopes=list(payload.scopes),
        expires_at=payload.expires_at,
    )
    result: CreateApiKeyResult = await create_api_key(
        cmd, uow=uow, actor_permissions=actor_permissions
    )
    return CreateApiKeyOut(
        api_key=_ApiKeyOut(**result.api_key.to_dict()),
        plaintext=result.plaintext,
    )


@router.delete(
    "/{api_key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke API key",
)
async def revoke_api_key_endpoint(
    api_key_id: str,
    uow: UnitOfWorkDep,
    actor_permissions: ActorPermissionsDep,
    user_id: CurrentUserIdDep,
) -> None:
    cmd = RevokeApiKeyCommand(user_id=user_id, api_key_id=api_key_id)
    await revoke_api_key(cmd, uow=uow, actor_permissions=actor_permissions)
    return None
