"""OpenTelemetry setup.

We provide a no-op default if OpenTelemetry is disabled (typical for tests
and local dev). When enabled, traces are exported via OTLP gRPC.
"""

from __future__ import annotations

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from ..settings import get_settings

_initialized = False


def configure_telemetry() -> None:
    """Set up OpenTelemetry tracing. Idempotent."""
    global _initialized
    if _initialized:
        return

    settings = get_settings()
    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": settings.app_version,
            "deployment.environment": settings.app_env,
        }
    )

    if settings.otel_enabled:
        provider = TracerProvider(resource=resource)
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )

            exporter = OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        except Exception:  # noqa: BLE001 - best effort
            # Fall back to in-memory only
            pass
        trace.set_tracer_provider(provider)

    _initialized = True


def get_tracer(name: str) -> trace.Tracer:
    """Return a tracer with the given name."""
    if not _initialized:
        configure_telemetry()
    return trace.get_tracer(name)
