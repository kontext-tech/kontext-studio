"""Persisted chat upload-preparation payload helpers.

The chat upload preparation workflow stores camel-cased metadata inside the
root run's engine metadata JSON and reports per-step results through the
shared schema models. This module owns the tolerant parsing and writing of
those payloads so :mod:`kontext.api.services.chats` stays focused on service
calls. Wire request/response models themselves come from ``kontext.schema``
(the generated contract); nothing here defines a new wire format.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from pydantic.alias_generators import to_camel

from kontext.file.lakehouse_ingest_models import LakehouseIngestResultData
from kontext.jobs import parse_engine_metadata_json
from kontext.schema import (
    ChatAttachmentContextFile,
    ChatAttachmentContextTable,
    ChatUploadPreparationAcceptedFile,
    ChatUploadPreparationFailure,
)

CHAT_UPLOAD_PREPARATION_WORKFLOW_KEY = "chat_upload_preparation"
CHAT_UPLOAD_PREPARATION_METADATA_KEY = "chatUploadPreparation"


def _parse_json_value(value: str | Mapping[str, Any] | None) -> Any | None:
    if isinstance(value, Mapping):
        return dict(value)
    if not isinstance(value, str) or not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return None


def parse_payload_model[TModel: BaseModel](
    value: str | Mapping[str, Any] | BaseModel | None,
    model_type: type[TModel],
) -> TModel | None:
    """Validate a persisted JSON/JSON-model payload; ``None`` on any mismatch."""
    if value is None:
        return None
    if isinstance(value, model_type):
        return value

    payload: Any
    if isinstance(value, BaseModel):
        payload = value.model_dump()
    elif isinstance(value, str | Mapping):
        payload = _parse_json_value(value)
    else:
        payload = value

    if payload is None:
        return None

    try:
        return model_type.model_validate(payload)
    except ValidationError:
        return None


def _as_optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def as_optional_uuid_str(value: Any) -> str | None:
    text = _as_optional_str(value)
    if text is None:
        return None
    try:
        return str(UUID(text))
    except (TypeError, ValueError):
        return None


def classify_chat_upload_failure_code(error: str) -> str | None:
    normalized_error = error.lower()
    if "allow overwrite" in normalized_error or "already exists" in normalized_error:
        return "already_exists"
    return None


def normalize_chat_upload_failure(
    *,
    filename: str | None,
    error: str,
    file_id: str | None = None,
    code: str | None = None,
) -> ChatUploadPreparationFailure:
    return ChatUploadPreparationFailure(
        file_id=file_id,
        filename=filename,
        code=code or classify_chat_upload_failure_code(error),
        error=error,
    )


class _LooseChatUploadPreparationFailure(BaseModel):
    """Tolerant parser for persisted upload failure payloads."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True, alias_generator=to_camel)

    file_id: str | None = None
    filename: str | None = None
    code: str | None = None
    error: str = "Upload preparation failed"

    @field_validator("file_id", "filename", "code", mode="before")
    @classmethod
    def _coerce_optional_text(cls, value: Any) -> str | None:
        return _as_optional_str(value)

    @field_validator("error", mode="before")
    @classmethod
    def _coerce_error(cls, value: Any) -> str:
        return _as_optional_str(value) or "Upload preparation failed"


def _parse_chat_upload_accepted_files(
    value: Any,
) -> list[ChatUploadPreparationAcceptedFile]:
    if not isinstance(value, list):
        return []

    accepted_files: list[ChatUploadPreparationAcceptedFile] = []
    for entry in value:
        parsed = parse_payload_model(entry, ChatUploadPreparationAcceptedFile)
        if parsed is not None:
            accepted_files.append(parsed)
    return accepted_files


def _parse_chat_upload_failures(value: Any) -> list[ChatUploadPreparationFailure]:
    if not isinstance(value, list):
        return []

    failures: list[ChatUploadPreparationFailure] = []
    for entry in value:
        parsed = parse_payload_model(entry, ChatUploadPreparationFailure)
        if parsed is not None:
            failures.append(parsed)
            continue

        loose_failure = parse_payload_model(entry, _LooseChatUploadPreparationFailure)
        if loose_failure is None:
            continue

        failures.append(
            normalize_chat_upload_failure(
                filename=loose_failure.filename,
                error=loose_failure.error,
                file_id=as_optional_uuid_str(loose_failure.file_id),
                code=loose_failure.code,
            )
        )
    return failures


class ChatUploadPreparationMetadata(BaseModel):
    """Typed metadata stored on the chat upload preparation root run."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True, alias_generator=to_camel)

    internal_catalog_connection_id: str | None = None
    accepted_files: list[ChatUploadPreparationAcceptedFile] = Field(default_factory=list)
    upload_errors: list[ChatUploadPreparationFailure] = Field(default_factory=list)

    @field_validator("internal_catalog_connection_id", mode="before")
    @classmethod
    def _coerce_connection_id(cls, value: Any) -> str | None:
        return _as_optional_str(value)

    @field_validator("accepted_files", mode="before")
    @classmethod
    def _coerce_accepted_files(cls, value: Any) -> list[ChatUploadPreparationAcceptedFile]:
        return _parse_chat_upload_accepted_files(value)

    @field_validator("upload_errors", mode="before")
    @classmethod
    def _coerce_upload_errors(cls, value: Any) -> list[ChatUploadPreparationFailure]:
        return _parse_chat_upload_failures(value)


class _StoredLakehouseIngestJobResult(BaseModel):
    """Typed view over persisted Python job results for lakehouse ingest."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    success: bool | None = None
    message: str | None = None
    data: LakehouseIngestResultData | None = None
    error_code: str | None = None


def to_chat_upload_accepted_file(file_record) -> ChatUploadPreparationAcceptedFile:
    return ChatUploadPreparationAcceptedFile(
        file_id=str(file_record.id),
        filename=file_record.name,
        file_type=file_record.file_type,
        size=file_record.size,
    )


def parse_chat_upload_preparation_metadata(
    engine_metadata_json: str | None,
) -> ChatUploadPreparationMetadata | None:
    metadata = parse_engine_metadata_json(engine_metadata_json)
    return parse_payload_model(
        metadata.get(CHAT_UPLOAD_PREPARATION_METADATA_KEY),
        ChatUploadPreparationMetadata,
    )


def upsert_chat_upload_preparation_metadata_json(
    engine_metadata_json: str | None,
    *,
    internal_catalog_connection_id: str | None,
    accepted_files: list[ChatUploadPreparationAcceptedFile],
    upload_errors: list[ChatUploadPreparationFailure],
) -> str:
    metadata = parse_engine_metadata_json(engine_metadata_json)
    metadata[CHAT_UPLOAD_PREPARATION_METADATA_KEY] = ChatUploadPreparationMetadata(
        internal_catalog_connection_id=internal_catalog_connection_id,
        accepted_files=accepted_files,
        upload_errors=upload_errors,
    ).model_dump(by_alias=True, exclude_none=True)
    return json.dumps(metadata, default=str, sort_keys=True)


def parse_lakehouse_ingest_result_data(
    value: str | Mapping[str, Any] | None,
) -> LakehouseIngestResultData:
    envelope = parse_payload_model(value, _StoredLakehouseIngestJobResult)
    if envelope is not None and envelope.data is not None:
        return envelope.data

    direct_payload = parse_payload_model(value, LakehouseIngestResultData)
    return direct_payload or LakehouseIngestResultData()


def chat_attachment_file_from_accepted_file(
    accepted_file: ChatUploadPreparationAcceptedFile,
) -> ChatAttachmentContextFile:
    return ChatAttachmentContextFile(
        file_id=accepted_file.file_id,
        file_name=accepted_file.filename,
        file_type=accepted_file.file_type,
    )


def chat_attachment_tables_from_catalog_details(
    *,
    file_id: str,
    entity_details,
) -> list[ChatAttachmentContextTable]:
    tables: list[ChatAttachmentContextTable] = []
    for detail in entity_details:
        entity = getattr(detail, "entity", None)
        if entity is None:
            continue
        tables.append(
            ChatAttachmentContextTable(
                file_id=file_id,
                entity_id=str(entity.id),
                namespace_name=str(entity.namespace_name),
                entity_name=str(entity.entity_name),
                row_count=entity.row_count,
                column_names=[
                    str(column.name)
                    for column in getattr(detail, "columns", []) or []
                    if getattr(column, "name", None)
                ],
            )
        )
    return tables
