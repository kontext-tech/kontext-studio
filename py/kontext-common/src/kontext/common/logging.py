# ruff: noqa: I001

"""Structured logging utilities.

This module provides a small, dependency-light way to emit single-line JSON logs
that work well with CloudWatch (including exception stack traces as escaped\n).

Design goals:
- Safe to call multiple times (idempotent per-process)
- Avoid surprising behavior changes (keeps uvicorn access logger propagation)
- Keep configuration centralized for API + worker
"""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any

from pythonjsonlogger.json import JsonFormatter  # pyright: ignore[reportMissingImports]

from kontext.common.config import get_config


_CONFIGURED: bool = False


class _CompactJsonFormatter(JsonFormatter):
    """JSON formatter that excludes null/None attributes to save space."""

    def process_log_record(self, log_data: dict[str, Any]) -> dict[str, Any]:
        # Filter out None values to keep logs compact
        return {key: value for key, value in log_data.items() if value is not None}


class _AutoExcInfoFilter(logging.Filter):
    """Filter that automatically includes exc_info for ERROR and CRITICAL
    when in exception context."""

    def filter(self, record: logging.LogRecord) -> bool:
        # If logging at ERROR or CRITICAL level and there's an active exception,
        # automatically include exc_info if not explicitly set
        if (
            record.levelno >= logging.ERROR
            and record.exc_info is None
            and sys.exc_info()[0] is not None
        ):
            record.exc_info = sys.exc_info()
        return True


class _ServiceNameFilter(logging.Filter):
    def __init__(self, service_name: str) -> None:
        super().__init__()
        self._service_name = service_name

    def filter(self, record: logging.LogRecord) -> bool:
        record.service = self._service_name
        return True


def _parse_log_level(value: str | None) -> int:
    if not value:
        return logging.INFO
    return getattr(logging, value.upper(), logging.INFO)


def configure_structured_logging(
    *, service_name: str, log_level: str | None = None, log_format: str | None = None
) -> None:
    """Configure process-wide logging.

    Controlled via env vars by default:
    - `LOG_LEVEL` (default: INFO)
    - `LOG_FORMAT` (default: json) values: json|plain

    Args:
        service_name: Logical service name included on each log record.
        log_level: Override log level (else uses env/default).
        log_format: Override format (else uses env/default).
    """

    global _CONFIGURED
    if _CONFIGURED:
        return

    config = get_config()
    resolved_level = _parse_log_level(log_level or config.log_level or "INFO")
    resolved_format = (log_format or config.log_format or "json").lower()

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(resolved_level)

    # Ensure root has at least one handler.
    if not root_logger.handlers:
        handler = logging.StreamHandler(stream=sys.stdout)
        root_logger.addHandler(handler)

    if resolved_format == "json":
        formatter = _CompactJsonFormatter(
            fmt=("%(asctime)s %(levelname)s %(name)s %(service)s %(message)s %(exc_info)s"),
            rename_fields={"asctime": "timestamp", "levelname": "level"},
            datefmt="%Y-%m-%dT%H:%M:%SZ",
        )
        # Use UTC timestamps
        formatter.converter = time.gmtime

        service_filter = _ServiceNameFilter(service_name)
        exc_info_filter = _AutoExcInfoFilter()

        # Consolidate root handlers to avoid duplicates if multiple exist
        # (e.g. from basicConfig)
        if len(root_logger.handlers) > 1:
            for existing_handler in list(root_logger.handlers)[1:]:
                root_logger.removeHandler(existing_handler)

        # Apply to root handlers and add filters.
        for handler in root_logger.handlers:
            handler.setFormatter(formatter)
            handler.addFilter(service_filter)
            handler.addFilter(exc_info_filter)

        # Also try to align common framework loggers.
        # We force them to propagate to root so they use our single JSON handler.
        # To avoid duplicates, we remove any existing handlers they might have.
        # Harness-owned loggers are supplied via env (see ModelEnvVars
        # .AGENT_FRAMEWORK_LOGGERS) so this layer stays framework-neutral and a
        # harness swap does not require editing kontext-common.
        framework_loggers = [
            "uvicorn",
            "uvicorn.error",
            "fastapi",
            "httpx",
            "openai",
        ]
        extra_loggers_env = os.getenv("KONTEXT_AGENT_FRAMEWORK_LOGGERS", "")
        framework_loggers.extend(
            name.strip() for name in extra_loggers_env.split(",") if name.strip()
        )
        for logger_name in framework_loggers:
            framework_logger = logging.getLogger(logger_name)
            framework_logger.setLevel(resolved_level)

            # Remove existing handlers to avoid double-logging when propagating to root
            if framework_logger.handlers:
                for handler in list(framework_logger.handlers):
                    framework_logger.removeHandler(handler)

            framework_logger.propagate = True

        # Catch-all: ensure any other logger that has handlers uses our formatter
        for name in logging.root.manager.loggerDict:
            extra_logger = logging.getLogger(name)
            if hasattr(extra_logger, "handlers") and extra_logger.handlers:
                for handler in extra_logger.handlers:
                    handler.setFormatter(formatter)
                    handler.addFilter(service_filter)
                    handler.addFilter(exc_info_filter)

        # Uvicorn access logs are high-volume; make them JSON too if explicitly enabled.
        if (os.getenv("UVICORN_ACCESS_LOG_FORMAT") or "").lower() == "json":
            access_logger = logging.getLogger("uvicorn.access")
            access_logger.setLevel(resolved_level)
            for handler in access_logger.handlers:
                handler.setFormatter(formatter)
                handler.addFilter(service_filter)
                handler.addFilter(exc_info_filter)

    _CONFIGURED = True
