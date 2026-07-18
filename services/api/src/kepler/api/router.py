"""V1 API router."""

from __future__ import annotations

from fastapi import APIRouter

from .v1.api_keys import router as api_keys_router
from .v1.auth import router as auth_router
from .v1.users import router as users_router
from .v1.workspaces import router as workspaces_router

api_v1_router = APIRouter(prefix="/v1")
api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(workspaces_router)
api_v1_router.include_router(api_keys_router)
