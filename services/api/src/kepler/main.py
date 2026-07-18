"""FastAPI application factory and entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.requests import Request

from .api.router import api_v1_router
from .core.logging import configure_logging, get_logger
from .core.middleware.access_log import AccessLogMiddleware
from .core.middleware.csp import CSPNonceMiddleware
from .core.middleware.error_handler import ErrorHandlerMiddleware
from .core.middleware.request_id import RequestIdMiddleware
from .core.middleware.security_headers import SecurityHeadersMiddleware
from .core.security.jwt import get_jwt_service
from .core.telemetry import configure_telemetry
from .infra.cache.redis import get_redis_client, reset_redis_client
from .infra.cache.refresh_store import reset_refresh_token_store
from .infra.db.session import reset_session_factory
from .settings import get_settings

_log = get_logger("kepler.main")


def _install_openapi_security(app: FastAPI) -> None:
    """Register security schemes and a default security requirement.

    We override `app.openapi` to inject the security schemes and apply a
    default security requirement to every operation (auth is required
    unless an endpoint explicitly opts out).
    """
    bearer_scheme: dict[str, str] = {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "JWT",
        "description": "RS256 access token issued by /v1/auth/sign-in.",
    }
    apikey_scheme: dict[str, str] = {
        "type": "apiKey",
        "in": "header",
        "name": "Authorization",
        "description": (
            "Use `Authorization: ApiKey kpk_...` for machine-to-machine auth. "
            "Issued via `POST /v1/users/me/api-keys`."
        ),
    }
    public_paths = {"/", "/healthz", "/readyz", "/docs", "/redoc", "/openapi.json", "/.well-known/jwks.json"}

    def _custom_openapi() -> dict:
        if app.openapi_schema:
            return app.openapi_schema
        from fastapi.openapi.utils import get_openapi

        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        components = schema.setdefault("components", {})
        schemes = components.setdefault("securitySchemes", {})
        schemes["BearerAuth"] = bearer_scheme
        schemes["ApiKeyAuth"] = apikey_scheme
        for path, ops in schema.get("paths", {}).items():
            if path in public_paths:
                continue
            for method, op in ops.items():
                if method.lower() not in {"get", "post", "put", "patch", "delete"}:
                    continue
                if "security" in op and op["security"] is not None:
                    continue
                op["security"] = [{"BearerAuth": []}, {"ApiKeyAuth": []}]
        app.openapi_schema = schema
        return schema

    app.openapi = _custom_openapi  # type: ignore[method-assign]


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan: configure services on startup, dispose on shutdown."""
    settings = get_settings()
    configure_logging()
    configure_telemetry()
    _log.info(
        "startup",
        app_env=settings.app_env,
        app_version=settings.app_version,
        service=settings.otel_service_name,
    )
    # Pre-warm the JWT service so the first request isn't slow.
    get_jwt_service()
    try:
        yield
    finally:
        _log.info("shutdown")
        reset_session_factory()
        await reset_redis_client()


def create_app() -> FastAPI:
    """Application factory."""
    settings = get_settings()
    configure_logging()

    app = FastAPI(
        title="Kepler Vision API",
        version=settings.app_version,
        description="AI-powered Earth Observation platform — auth & identity (Sprint 1).",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=_lifespan,
    )

    # P1.6: register OpenAPI security schemes and a default security
    # requirement so every protected endpoint documents the auth.
    _install_openapi_security(app)

    # Middleware order: outermost added last. We want request_id to wrap
    # everything, error_handler to catch anything below it, then access_log,
    # then security headers + CSP, then CORS.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(CSPNonceMiddleware)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(ErrorHandlerMiddleware)
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.http_cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-Id", "X-Tenant-Id", "X-Workspace-Id"],
        expose_headers=["X-Request-Id", "Retry-After", "X-CSP-Nonce", "X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"],
    )

    # Routers
    from .api.router import api_v1_router as _api_v1

    app.include_router(_api_v1)

    # Health
    @app.get("/healthz", tags=["health"], include_in_schema=False)
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz", tags=["health"])
    async def readyz() -> JSONResponse:
        """Readiness: check DB, Redis, JWKS."""
        checks: dict[str, str] = {}
        ok = True

        # DB
        try:
            from sqlalchemy import text as _text

            from .infra.db.session import get_session_factory

            factory = get_session_factory()
            async with factory() as session:
                await session.execute(_text("SELECT 1"))
            checks["database"] = "ok"
        except Exception as exc:  # noqa: BLE001
            ok = False
            checks["database"] = f"error: {exc.__class__.__name__}"

        # Redis
        try:
            client = get_redis_client()
            await client.ping()
            checks["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            ok = False
            checks["redis"] = f"error: {exc.__class__.__name__}"

        # JWT
        try:
            get_jwt_service().jwks()
            checks["jwt"] = "ok"
        except Exception as exc:  # noqa: BLE001
            ok = False
            checks["jwt"] = f"error: {exc.__class__.__name__}"

        return JSONResponse(
            status_code=200 if ok else 503,
            content={"status": "ok" if ok else "degraded", "checks": checks},
        )

    @app.get("/metrics", tags=["health"], include_in_schema=False)
    async def metrics() -> JSONResponse:
        return JSONResponse(content={}, media_type=CONTENT_TYPE_LATEST)

    @app.get("/.well-known/jwks.json", tags=["auth"], include_in_schema=False)
    async def jwks_endpoint() -> dict[str, object]:
        return get_jwt_service().jwks()

    @app.get("/", tags=["meta"], include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "env": settings.app_env,
        }

    _log.info("app_created", app_env=settings.app_env)
    return app


app = create_app()


# P1.6: Install security schemes + a default security requirement on every
# protected operation. We call this after `create_app` so the app instance
# is fully wired (routes, middleware) when the OpenAPI schema is generated.
_install_openapi_security(app)


def run() -> None:
    """Entry point for `python -m kepler.main`."""
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "kepler.main:app",
        host=settings.http_host,
        port=settings.http_port,
        reload=settings.app_env == "development",
    )


if __name__ == "__main__":  # pragma: no cover
    run()
