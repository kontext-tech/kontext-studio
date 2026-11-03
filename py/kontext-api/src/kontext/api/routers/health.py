"""
Health check and monitoring endpoints.
"""

import logging

from fastapi import APIRouter

from kontext.common.utils.datetime_utils import utc_now
from kontext.data import check_database_connectivity
from kontext.schema import HealthCheckResponse, PingResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthCheckResponse, operation_id="HealthCheck")
def health_check() -> HealthCheckResponse:
    """
    Comprehensive health check endpoint with dependency testing.

    Tests:
    - Project database connectivity (SQLite in local mode, PostgreSQL in cloud mode)

    Returns:
        HealthCheckResponse with status and dependency checks
    """
    logger.debug("Health check requested")

    errors = []
    is_healthy = True

    db_healthy, db_error = check_database_connectivity()
    if not db_healthy:
        is_healthy = False
        errors.append(db_error)

    status = "healthy" if is_healthy else "unhealthy"

    return HealthCheckResponse(
        status=status,
        timestamp=utc_now(),
        version="1.0.0",
        error="; ".join(errors) if errors else None,
    )


@router.get("/ping", response_model=PingResponse, operation_id="Ping")
def ping() -> PingResponse:
    """
    Simple ping/pong endpoint for liveness checks.

    Returns:
        PingResponse with timestamp
    """
    logger.debug("Ping requested")
    return PingResponse(status="pong")
