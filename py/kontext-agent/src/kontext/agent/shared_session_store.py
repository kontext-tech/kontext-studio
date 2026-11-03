"""Shared session-state helpers for lightweight cross-agent coordination."""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel

from kontext.common.utils.datetime_utils import utc_now_iso
from kontext.schema import ArtifactType, AttachedDataSource

logger = logging.getLogger(__name__)

KONTEXT_SESSION_NAMESPACE = "kontext"
KONTEXT_SESSION_VERSION = 1
KONTEXT_SESSION_VERSION_KEY = "version"
KONTEXT_SESSION_ARTIFACTS_KEY = "artifacts_by_id"
KONTEXT_SESSION_DATA_IDENTITY_INDEX_KEY = "data_identity_index"
KONTEXT_SESSION_ARTIFACT_ALIASES_KEY = "artifact_aliases"
KONTEXT_SESSION_ATTACHED_DATA_SOURCES_KEY = "attached_data_sources"
KONTEXT_SESSION_CURRENT_EXECUTION_RUN_ID_KEY = "current_execution_run_id"


class SharedArtifactDescriptor(BaseModel):
    """Lightweight persisted artifact metadata shared across team members."""

    artifact_id: str
    artifact_type: ArtifactType
    title: str | None = None
    sql: str | None = None
    identity_key: str | None = None
    created_at: str | None = None
    modified_at: str | None = None
    row_count: int | None = None
    column_names: list[str] | None = None


def create_kontext_session_state(
    attached_data_sources: list[AttachedDataSource] | None = None,
) -> dict[str, Any]:
    """Create an empty, versioned shared session-state structure."""
    return {
        KONTEXT_SESSION_NAMESPACE: {
            KONTEXT_SESSION_VERSION_KEY: KONTEXT_SESSION_VERSION,
            KONTEXT_SESSION_ARTIFACTS_KEY: {},
            KONTEXT_SESSION_DATA_IDENTITY_INDEX_KEY: {},
            KONTEXT_SESSION_ARTIFACT_ALIASES_KEY: {},
            KONTEXT_SESSION_ATTACHED_DATA_SOURCES_KEY: [
                source.model_dump(mode="json") for source in (attached_data_sources or [])
            ],
        }
    }


class SharedSessionStore:
    """Typed wrapper over a mutable session-state mapping for shared metadata."""

    def __init__(self, session_state: dict[str, Any]):
        self.session_state = session_state
        self._namespace = self._ensure_namespace()

    @classmethod
    def from_session_state(cls, session_state: dict[str, Any] | None) -> SharedSessionStore | None:
        """Construct a store when mutable session state is available."""
        if session_state is None:
            return None
        return cls(session_state)

    def _ensure_namespace(self) -> dict[str, Any]:
        namespace = self.session_state.get(KONTEXT_SESSION_NAMESPACE)
        if not isinstance(namespace, dict):
            namespace = create_kontext_session_state()[KONTEXT_SESSION_NAMESPACE]
            self.session_state[KONTEXT_SESSION_NAMESPACE] = namespace

        namespace.setdefault(KONTEXT_SESSION_VERSION_KEY, KONTEXT_SESSION_VERSION)
        namespace.setdefault(KONTEXT_SESSION_ARTIFACTS_KEY, {})
        namespace.setdefault(KONTEXT_SESSION_DATA_IDENTITY_INDEX_KEY, {})
        namespace.setdefault(KONTEXT_SESSION_ARTIFACT_ALIASES_KEY, {})
        namespace.setdefault(KONTEXT_SESSION_ATTACHED_DATA_SOURCES_KEY, [])

        if not isinstance(namespace[KONTEXT_SESSION_ARTIFACTS_KEY], dict):
            namespace[KONTEXT_SESSION_ARTIFACTS_KEY] = {}
        if not isinstance(namespace[KONTEXT_SESSION_DATA_IDENTITY_INDEX_KEY], dict):
            namespace[KONTEXT_SESSION_DATA_IDENTITY_INDEX_KEY] = {}
        if not isinstance(namespace[KONTEXT_SESSION_ARTIFACT_ALIASES_KEY], dict):
            namespace[KONTEXT_SESSION_ARTIFACT_ALIASES_KEY] = {}
        if not isinstance(namespace[KONTEXT_SESSION_ATTACHED_DATA_SOURCES_KEY], list):
            namespace[KONTEXT_SESSION_ATTACHED_DATA_SOURCES_KEY] = []

        self._namespace = namespace
        return namespace

    def _artifacts_by_id(self) -> dict[str, Any]:
        return self._namespace[KONTEXT_SESSION_ARTIFACTS_KEY]

    def _data_identity_index(self) -> dict[str, Any]:
        return self._namespace[KONTEXT_SESSION_DATA_IDENTITY_INDEX_KEY]

    def _artifact_aliases(self) -> dict[str, Any]:
        return self._namespace[KONTEXT_SESSION_ARTIFACT_ALIASES_KEY]

    def get_current_execution_run_id(self) -> str | None:
        """Return the active execution-run binding when present."""
        value = self._namespace.get(KONTEXT_SESSION_CURRENT_EXECUTION_RUN_ID_KEY)
        if isinstance(value, str) and value.strip():
            return value
        return None

    def bind_current_execution_run_id(self, run_id: str | None) -> None:
        """Set or clear the execution-run binding for downstream tool calls."""
        if run_id and run_id.strip():
            self._namespace[KONTEXT_SESSION_CURRENT_EXECUTION_RUN_ID_KEY] = run_id
            return

        self._namespace.pop(KONTEXT_SESSION_CURRENT_EXECUTION_RUN_ID_KEY, None)

    def upsert_artifact_descriptor(
        self,
        *,
        artifact_id: str,
        artifact_type: ArtifactType,
        title: str | None = None,
        sql: str | None = None,
        identity_key: str | None = None,
        row_count: int | None = None,
        column_names: list[str] | None = None,
    ) -> SharedArtifactDescriptor:
        """Create or update a shared artifact descriptor keyed by durable artifact ID."""
        existing = self.get_artifact_descriptor(artifact_id)
        now_iso = utc_now_iso()
        descriptor = SharedArtifactDescriptor(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            title=title if title is not None else (existing.title if existing else None),
            sql=sql if sql is not None else (existing.sql if existing else None),
            identity_key=identity_key
            if identity_key is not None
            else (existing.identity_key if existing else None),
            created_at=existing.created_at if existing else now_iso,
            modified_at=now_iso,
            row_count=row_count
            if row_count is not None
            else (existing.row_count if existing else None),
            column_names=column_names
            if column_names is not None
            else (existing.column_names if existing else None),
        )
        self._artifacts_by_id()[artifact_id] = descriptor.model_dump(mode="json")

        if artifact_type == ArtifactType.DATATABLE and descriptor.identity_key:
            self._data_identity_index()[descriptor.identity_key] = artifact_id

        return descriptor

    def register_artifact_alias(self, alias_id: str, artifact_id: str) -> str:
        """Record a stable alias that resolves to a durable artifact ID."""
        self._artifact_aliases()[alias_id] = artifact_id
        return artifact_id

    def resolve_artifact_id(self, artifact_id_or_alias: str) -> str | None:
        """Resolve a durable artifact ID from either the ID itself or an alias."""
        if artifact_id_or_alias in self._artifacts_by_id():
            return artifact_id_or_alias

        alias_target = self._artifact_aliases().get(artifact_id_or_alias)
        if isinstance(alias_target, str):
            return alias_target
        return None

    def get_artifact_descriptor(self, artifact_id: str) -> SharedArtifactDescriptor | None:
        """Return a descriptor for a durable artifact ID."""
        resolved_id = self.resolve_artifact_id(artifact_id) or artifact_id
        raw_descriptor = self._artifacts_by_id().get(resolved_id)
        if not isinstance(raw_descriptor, dict):
            return None
        try:
            return SharedArtifactDescriptor.model_validate(raw_descriptor)
        except Exception as exc:
            logger.warning("Failed to parse shared artifact descriptor %s: %s", artifact_id, exc)
            return None

    def list_artifact_descriptors(
        self,
        artifact_type: ArtifactType | None = None,
    ) -> list[SharedArtifactDescriptor]:
        """List all shared artifact descriptors, optionally filtered by type."""
        descriptors: list[SharedArtifactDescriptor] = []
        for artifact_id in self._artifacts_by_id():
            descriptor = self.get_artifact_descriptor(artifact_id)
            if descriptor is None:
                continue
            if artifact_type is not None and descriptor.artifact_type != artifact_type:
                continue
            descriptors.append(descriptor)
        return descriptors

    def find_data_artifact_by_identity(self, identity_key: str) -> SharedArtifactDescriptor | None:
        """Resolve a data-table artifact descriptor by result identity key."""
        artifact_id = self._data_identity_index().get(identity_key)
        if not isinstance(artifact_id, str):
            return None
        descriptor = self.get_artifact_descriptor(artifact_id)
        if descriptor is None or descriptor.artifact_type != ArtifactType.DATATABLE:
            return None
        return descriptor
