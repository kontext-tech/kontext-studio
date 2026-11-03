"""Shared exceptions for query orchestration."""


class QueryServiceError(Exception):
    """Application-level error with HTTP-style status metadata."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail
