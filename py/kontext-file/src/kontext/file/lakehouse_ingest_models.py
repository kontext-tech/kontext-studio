"""Typed payload models for lakehouse ingest job results."""

from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class _LakehouseIngestModel(BaseModel):
    """Shared configuration for serialized lakehouse ingest payloads."""

    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
    )


class LakehouseIngestFailure(_LakehouseIngestModel):
    """A single file-level ingest failure."""

    file_id: str | None = Field(
        default=None,
        validation_alias=AliasChoices("id", "fileId", "file_id"),
    )
    error: str = "Lakehouse ingest failed"

    @field_validator("file_id", mode="before")
    @classmethod
    def _coerce_file_id(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("error", mode="before")
    @classmethod
    def _coerce_error(cls, value: Any) -> str:
        if value is None:
            return "Lakehouse ingest failed"
        text = str(value).strip()
        return text or "Lakehouse ingest failed"

    def to_job_result_payload(self) -> dict[str, str]:
        payload = {"error": self.error}
        if self.file_id is not None:
            payload["id"] = self.file_id
        return payload


class LakehouseIngestResultData(_LakehouseIngestModel):
    """Structured result payload persisted for lakehouse ingest job runs."""

    connection_id: str | None = None
    successful_file_ids: list[str] = Field(default_factory=list)
    failed_files: list[LakehouseIngestFailure] = Field(default_factory=list)
    entity_count: int | None = None
    invalidated_session_ids: list[str] = Field(default_factory=list)

    @field_validator("connection_id", mode="before")
    @classmethod
    def _coerce_connection_id(cls, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @field_validator("successful_file_ids", mode="before")
    @classmethod
    def _coerce_successful_file_ids(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if item is not None and str(item).strip()]

    @field_validator("failed_files", mode="before")
    @classmethod
    def _coerce_failed_files(cls, value: Any) -> list[LakehouseIngestFailure]:
        if not isinstance(value, list):
            return []

        failures: list[LakehouseIngestFailure] = []
        for item in value:
            try:
                failures.append(LakehouseIngestFailure.model_validate(item))
            except Exception:
                continue
        return failures

    @field_validator("invalidated_session_ids", mode="before")
    @classmethod
    def _coerce_invalidated_session_ids(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if item is not None and str(item).strip()]

    def to_job_result_payload(self) -> dict[str, Any]:
        return {
            "connection_id": self.connection_id,
            "successful_file_ids": list(self.successful_file_ids),
            "failed_files": [failure.to_job_result_payload() for failure in self.failed_files],
            "entity_count": self.entity_count,
            "invalidated_session_ids": list(self.invalidated_session_ids),
        }
