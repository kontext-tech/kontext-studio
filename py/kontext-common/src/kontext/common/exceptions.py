"""Shared transport-neutral exceptions for Kontext Python packages."""

from __future__ import annotations


class KontextError(Exception):
    """Base exception for domain and application-layer failures."""

    status_code = 500
    title = "Internal Server Error"

    def __init__(self, detail: str, *, problem_type: str | None = None):
        super().__init__(detail)
        self.detail = detail
        self.problem_type = problem_type


class BadRequestError(KontextError):
    status_code = 400
    title = "Bad Request"


class UnauthorizedError(KontextError):
    status_code = 401
    title = "Unauthorized"


class ForbiddenError(KontextError):
    status_code = 403
    title = "Forbidden"


class NotFoundError(KontextError):
    status_code = 404
    title = "Not Found"


class ConflictError(KontextError):
    status_code = 409
    title = "Conflict"


class TransientServiceError(KontextError):
    """Retryable service failure (e.g. a lock timeout, network blip, 5xx).

    Provider and service implementations raise this to signal that the
    *operation* may be retried; every other error is treated as permanent.
    Workers and job executors rely on this distinction to decide between
    retrying a control-plane update and failing the run.
    """

    status_code = 503
    title = "Service Unavailable"
