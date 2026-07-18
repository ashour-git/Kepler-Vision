"""Structured logging with structlog.

We emit one JSON object per line in production, and a colored console
formatter in development. Request context (request_id, tenant_id, user_id)
is injected by the request middleware via contextvars.
"""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from typing import Any

import structlog
from structlog.contextvars import bind_contextvars, clear_contextvars, merge_contextvars
from structlog.typing import EventDict, Processor

from ..settings import get_settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
tenant_id_var: ContextVar[str | None] = ContextVar("tenant_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


def _add_context(_: Any, __: str, event_dict: EventDict) -> EventDict:
    """Inject request context into every log record."""
    if (rid := request_id_var.get()) is not None:
        event_dict.setdefault("request_id", rid)
    if (tid := tenant_id_var.get()) is not None:
        event_dict.setdefault("tenant_id", tid)
    if (uid := user_id_var.get()) is not None:
        event_dict.setdefault("user_id", uid)
    return event_dict


def _safe_add_logger_name(_: Any, __: str, event_dict: EventDict) -> EventDict:
    """Add a logger name, falling back gracefully when the factory is PrintLogger."""
    name = event_dict.pop("logger_name", None) or "kepler"
    event_dict.setdefault("logger", name)
    return event_dict


def configure_logging() -> None:
    """Configure structlog and stdlib logging. Idempotent."""
    settings = get_settings()
    level = getattr(logging, settings.log_level)

    shared_processors: list[Processor] = [
        merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        _add_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.log_format == "json":
        renderer: Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Quiet down noisy libraries
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "aiosqlite"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.basicConfig(level=level, format="%(message)s", stream=sys.stdout)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound logger with the given name."""
    return structlog.get_logger(name) if name else structlog.get_logger()


__all__ = [
    "bind_contextvars",
    "clear_contextvars",
    "configure_logging",
    "get_logger",
    "request_id_var",
    "tenant_id_var",
    "user_id_var",
]
