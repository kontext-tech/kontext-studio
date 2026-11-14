"""
OpenTelemetry (OTLP) setup for the Kontext Console local server.

Behaviour
---------
- Reads ``OTEL_EXPORTER_OTLP_ENDPOINT`` (e.g. ``http://localhost:4318``).
  When set, traces are exported via OTLP HTTP.
- When not set, traces are exported to stdout as a development fallback so
  distributed tracing is visible without a collector.
- If the ``opentelemetry`` packages are not installed, the function is a no-op
  and a debug message is logged (graceful degradation).

Env vars honoured
-----------------
OTEL_EXPORTER_OTLP_ENDPOINT   OTLP collector HTTP endpoint (optional)
OTEL_SERVICE_NAME             Service name override (default: kontext-studio)
OTEL_SDK_DISABLED             Set to "true" to skip all telemetry setup
"""

from __future__ import annotations

import importlib
import logging
import os

logger = logging.getLogger(__name__)


def configure_telemetry(service_name: str = "kontext-studio") -> None:
    """
    Set up OpenTelemetry tracing for the console process.

    Idempotent — safe to call multiple times; subsequent calls are no-ops.

    Args:
        service_name: Logical service name emitted with every span.
    """
    if os.getenv("OTEL_SDK_DISABLED", "false").lower() == "true":
        logger.debug("OTEL_SDK_DISABLED=true — skipping telemetry setup")
        return

    try:
        trace = importlib.import_module("opentelemetry.trace")
        resources_module = importlib.import_module("opentelemetry.sdk.resources")
        trace_module = importlib.import_module("opentelemetry.sdk.trace")
        trace_export_module = importlib.import_module("opentelemetry.sdk.trace.export")
    except ImportError:
        logger.debug(
            "opentelemetry-sdk not installed — telemetry disabled. "
            "Install opentelemetry-sdk to enable OTLP tracing."
        )
        return

    Resource = resources_module.Resource
    TracerProvider = trace_module.TracerProvider
    BatchSpanProcessor = trace_export_module.BatchSpanProcessor

    # Guard against double-initialisation (e.g. when uvicorn --reload restarts).
    existing = trace.get_tracer_provider()
    if not isinstance(existing, trace.ProxyTracerProvider):
        # A real provider is already registered — skip silently.
        return

    resolved_service = os.getenv("OTEL_SERVICE_NAME", service_name)
    resource = Resource.create({"service.name": resolved_service})

    provider = TracerProvider(resource=resource)

    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    if otlp_endpoint:
        try:
            OTLPSpanExporter = importlib.import_module(
                "opentelemetry.exporter.otlp.proto.http.trace_exporter"
            )
            OTLPSpanExporter = OTLPSpanExporter.OTLPSpanExporter

            exporter = OTLPSpanExporter(endpoint=f"{otlp_endpoint.rstrip('/')}/v1/traces")
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info(
                "OpenTelemetry OTLP tracing enabled: endpoint=%s service=%s",
                otlp_endpoint,
                resolved_service,
            )
        except ImportError:
            logger.warning(
                "opentelemetry-exporter-otlp-proto-http not installed. "
                "Set OTEL_EXPORTER_OTLP_ENDPOINT requires "
                "`opentelemetry-exporter-otlp-proto-http`. "
                "Falling back to stdout exporter."
            )
            otlp_endpoint = ""

    if not otlp_endpoint:
        ConsoleSpanExporter = trace_export_module.ConsoleSpanExporter
        SimpleSpanProcessor = trace_export_module.SimpleSpanProcessor

        provider.add_span_processor(SimpleSpanProcessor(ConsoleSpanExporter()))
        logger.debug(
            "OpenTelemetry stdout tracing enabled (dev mode). "
            "Set OTEL_EXPORTER_OTLP_ENDPOINT to export to a collector."
        )

    trace.set_tracer_provider(provider)

    # Instrument FastAPI if the instrumentation package is available.
    try:
        FastAPIInstrumentor = importlib.import_module(
            "opentelemetry.instrumentation.fastapi"
        ).FastAPIInstrumentor

        FastAPIInstrumentor().instrument()
        logger.debug("FastAPI OpenTelemetry instrumentation applied")
    except ImportError:
        pass  # optional — traces still work without request-level spans
