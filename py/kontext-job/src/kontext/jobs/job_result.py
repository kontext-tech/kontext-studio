"""
Job result models for Python jobs in Kontext
"""

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class JobResult:
    """Result object returned by Python job implementations"""

    success: bool
    message: str
    data: dict[str, Any] | None = None
    error_code: str | None = None

    def to_dict(self, include_data: bool = True) -> dict[str, Any]:
        """Convert result to dictionary for serialization

        Args:
            include_data: Whether to include the data attribute in the result
                         (default: True). Set to False for sensitive data like
                         SQL query results
        """
        result = {"success": self.success, "message": self.message}

        if include_data and self.data is not None:
            result["data"] = self.data
        elif not include_data and self.data is not None:
            # Keep metadata about the data for debugging
            result["data_removed"] = True
            result["data_type"] = type(self.data).__name__

        if self.error_code is not None:
            result["error_code"] = self.error_code

        return result

    def to_json(self) -> str:
        """Convert result to JSON string"""
        return json.dumps(self.to_dict(), default=str)

    @classmethod
    def success_result(cls, message: str, data: dict[str, Any] | None = None) -> "JobResult":
        """Create a successful result"""
        return cls(success=True, message=message, data=data)

    @classmethod
    def error_result(
        cls,
        message: str,
        error_code: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> "JobResult":
        """Create an error result"""
        return cls(success=False, message=message, error_code=error_code, data=data)

    @classmethod
    def from_exception(cls, exception: Exception) -> "JobResult":
        """Create an error result from an exception"""
        return cls.error_result(
            message=str(exception),
            error_code=exception.__class__.__name__,
            data={"exception_type": exception.__class__.__name__},
        )
