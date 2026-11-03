"""
SQLAlchemy models for project-scoped data.

This module contains database models stored in the project database.
Uses SQLAlchemy 2.0 style with Mapped[] for proper type hints.

Note: UUID fields use PostgreSQL's native UUID type for optimal performance.
Note: Enum fields (file_type, data_zone, object_type) are stored as strings,
matching the API string enums from kontext.schema.
Note: For timestamp/datetime fields, use `default=utc_now` instead of `func.now()`.
This ensures microsecond precision for proper ordering and consistency.
"""

from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from kontext.common.utils.datetime_utils import utc_now
from kontext.schema import JobTriggerType, QueryEngineType, QuerySessionStatus

from .database import Base

# =============================================================================
# Core Models
# =============================================================================


class Project(Base):
    """
    Represents a project in the project database.
    This is a cached copy of the complete project metadata from the Global API.
    """

    __tablename__ = "projects"
    __table_args__ = {"schema": "project"}

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    project_code: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    project_name: Mapped[str] = mapped_column(String(255), nullable=False)
    project_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    configuration: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Ownership and access
    owner_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    access_level: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Storage quota tracking
    used_storage_bytes: Mapped[int] = mapped_column(
        BigInteger, nullable=False, default=0, server_default="0"
    )

    # Audit trail
    date_created: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    modified_by_user_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    date_modified: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    date_deleted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Sync timestamp
    last_synced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


# =============================================================================
# Legacy Models (pre-existing, not refactored to preserve compatibility)
# =============================================================================


class ChatSession(Base):
    __tablename__ = "chat_sessions"
    __table_args__ = {"schema": "project"}

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    session_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    model_selection_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    resolved_model_config: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    query_session_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    default_catalog_connection_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    default_namespace: Mapped[str | None] = mapped_column(String(255), nullable=True)
    default_entity_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    engine_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    python_execution_approval_mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="always_ask",
        server_default="always_ask",
    )

    # Token usage stats
    tokens_inbound: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=0)
    tokens_outbound: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=0)

    # AuditableEntity fields
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=utc_now
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Owner ID (from IProjectEntity)
    owner_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)


class ChatSessionTokenUsage(Base):
    """Per-turn token consumption tracking with accurate temporal attribution.

    This table tracks token usage for each chat turn with a consumed_at timestamp,
    enabling accurate daily and monthly aggregation regardless of when the session was created.
    """

    __tablename__ = "chat_session_token_usage"
    __table_args__ = (
        Index("ix_chat_session_token_usage_consumed_at", "consumed_at"),
        Index("ix_chat_session_token_usage_project_consumed", "project_id", "consumed_at"),
        Index(
            "ix_chat_session_token_usage_session_consumed",
            "chat_session_id",
            "consumed_at",
        ),
        Index("ix_chat_session_token_usage_model_selection", "model_selection_id"),
        {"schema": "project"},
    )

    # Primary key
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)

    # References
    chat_session_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("project.chat_sessions.id"), nullable=False, index=True
    )
    job_run_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("project.job_runs.id"), nullable=True, index=True
    )
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)

    # Model info for aggregation
    model_selection_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)

    # Token counts (INCREMENTAL per turn, not cumulative)
    tokens_inbound: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    tokens_outbound: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)

    # Timestamps for accurate temporal tracking
    consumed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    # Relationships
    chat_session: Mapped["ChatSession"] = relationship("ChatSession")
    job_run: Mapped["JobRun | None"] = relationship("JobRun")


class ChatSessionAttachmentContext(Base):
    __tablename__ = "chat_session_attachment_contexts"
    __table_args__ = {"schema": "project"}

    chat_session_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("project.chat_sessions.id"),
        primary_key=True,
    )
    upload_preparation_run_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    internal_catalog_connection_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    files_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    tables_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )


class ChatSessionArtifact(Base):
    __tablename__ = "chat_session_artifacts"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "artifact_id",
            name="uq_chat_session_artifacts_session_artifact",
        ),
        {"schema": "project"},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    session_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("project.chat_sessions.id"), nullable=False, index=True
    )
    artifact_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    artifact_type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    meta: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class QuerySession(Base):
    """Query session metadata stored in project-scoped project database."""

    __tablename__ = "query_sessions"
    __table_args__ = {"schema": "project"}

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    session_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    catalog_connection_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    default_namespace: Mapped[str | None] = mapped_column(String(255), nullable=True)
    default_entity_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    owner_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=QuerySessionStatus.ACTIVE, index=True
    )
    engine_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=QueryEngineType.DUCKDB, index=True
    )
    # Job run ID for tracking initialization status
    job_run_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    database_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    # Content hash of the catalog snapshot this session materialized. Used to
    # detect a stale session when the catalog changes.
    catalog_revision: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Audit fields
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=utc_now
    )
    last_accessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Query(Base):
    """Query execution record stored in project-scoped project database."""

    __tablename__ = "queries"
    __table_args__ = {"schema": "project"}

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    code: Mapped[str] = mapped_column(String, nullable=False)  # SQL query text
    succeeded: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    record_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    message: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    owner_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    # FK to query_sessions
    session_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    # Job run ID for tracking query execution status
    job_run_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    duration_ms: Mapped[int] = mapped_column(BigInteger, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )


class CatalogConnection(Base):
    """Persisted catalog connection metadata."""

    __tablename__ = "catalog_connections"
    __table_args__ = {"schema": "project"}

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    provider_kind: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    connection_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    owner_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    source_category: Mapped[str | None] = mapped_column(String(32), nullable=True)
    auth_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    execution_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    connection_config_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    secret_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    secret_value: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    secret_configured: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    capabilities_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    # Content hash of the last synchronized normalized snapshot.
    catalog_revision: Mapped[str | None] = mapped_column(String(64), nullable=True)
    health_status: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_validated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    validation_error: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    sync_mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    sync_schedule: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=utc_now
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CatalogNamespace(Base):
    """Normalized namespace/schema under a catalog connection."""

    __tablename__ = "catalog_namespaces"
    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "namespace_name",
            name="uq_catalog_namespaces_connection_name",
        ),
        {"schema": "project"},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    connection_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("project.catalog_connections.id"), nullable=False, index=True
    )
    namespace_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=utc_now
    )


class CatalogEntity(Base):
    """Normalized table/view metadata under a catalog connection."""

    __tablename__ = "catalog_entities"
    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "namespace_id",
            "entity_name",
            name="uq_catalog_entities_connection_namespace_name",
        ),
        {"schema": "project"},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    connection_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("project.catalog_connections.id"), nullable=False, index=True
    )
    namespace_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("project.catalog_namespaces.id"), nullable=True, index=True
    )
    entity_name: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    row_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    location: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=utc_now
    )


class CatalogColumnRecord(Base):
    """Normalized column metadata under a catalog entity."""

    __tablename__ = "catalog_columns"
    __table_args__ = (
        UniqueConstraint(
            "entity_id",
            "column_name",
            name="uq_catalog_columns_entity_name",
        ),
        {"schema": "project"},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    entity_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("project.catalog_entities.id"), nullable=False, index=True
    )
    column_name: Mapped[str] = mapped_column(String(255), nullable=False)
    ordinal_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    data_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    nullable: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


class CatalogSyncState(Base):
    """Tracks the last sync status for a connection."""

    __tablename__ = "catalog_sync_states"
    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            name="uq_catalog_sync_states_connection",
        ),
        {"schema": "project"},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    connection_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("project.catalog_connections.id"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(64), nullable=False, default="pending")
    entity_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(String(4096), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )


class CatalogSourceLink(Base):
    """Normalized source-to-catalog-entity link."""

    __tablename__ = "catalog_source_links"
    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_id",
            "entity_id",
            name="uq_catalog_source_links_source_entity",
        ),
        {"schema": "project"},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_id: Mapped[UUID] = mapped_column(Uuid, nullable=False, index=True)
    connection_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("project.catalog_connections.id"), nullable=False, index=True
    )
    namespace_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("project.catalog_namespaces.id"), nullable=True, index=True
    )
    entity_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("project.catalog_entities.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class ProjectFile(Base):
    """
    Represents an uploaded file or link associated with a project.

    Table: files
    Schema: Matches .NET Kontext.Data.Models.ProjectFile
    Note: owner_id is nullable for ProjectFile
    """

    __tablename__ = "files"
    __table_args__ = (
        Index("ix_project_files_project_id_prefix_name", "project_id", "prefix", "name"),
        {"schema": "project"},
    )

    # Primary key
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)

    # Core fields
    name: Mapped[str] = mapped_column(String(1024), nullable=False)
    prefix: Mapped[str] = mapped_column(String(1024), nullable=False, default="", server_default="")
    uri: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    file_type: Mapped[str] = mapped_column(String(32), nullable=False, default="Default")
    content_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    size: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)  # long in .NET

    # Project association (IProjectEntity - nullable for ProjectFile)
    project_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)

    # Schema and statistics (JSON stored as text)
    schema_definition: Mapped[str | None] = mapped_column(Text, nullable=True)
    statistics_data: Mapped[str | None] = mapped_column(Text, nullable=True)

    # How this file record was produced (JSON ArtifactProvenance, camelCase)
    provenance: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Cached counts for quick UI access
    column_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_count: Mapped[int | None] = mapped_column(BigInteger, nullable=True)  # long in .NET

    # Timestamps for schema/stats updates
    last_schema_update: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_stats_update: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Audit fields (matching .NET OwnerNullableAuditableEntity - owner_id is nullable)
    owner_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    date_created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    date_modified: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=utc_now
    )
    modified_by_user_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    date_deleted: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# =============================================================================
# Project Event Model
# =============================================================================


class Event(Base):
    """
    Event entity for auditing project-scoped data operations.

    Table: events
    Purpose: Records project-scoped events for audit trail and job scheduling.

    Schema: Core fields match .NET Kontext.Data.Models.Event<TKey> structure for
    consistency with shared frontend components.
    Additional fields (is_processed, date_processed, processing_error) support
    event-driven job scheduling in project databases.

    Note: This is stored in each project's SQLite database.
    """

    __tablename__ = "events"
    __table_args__ = {"schema": "project"}

    # Primary key (UUID stored as string for SQLite compatibility)
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)

    # Event details - aligned with .NET Event model
    title: Mapped[str | None] = mapped_column(String(256), nullable=True)
    content: Mapped[str | None] = mapped_column(String(2560), nullable=True)

    # User and entity references
    user_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    project_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    content_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)

    # Event type - using string to store EventType enum value
    type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)

    # Channel type - using string to store ChannelType enum value
    channel_type: Mapped[str] = mapped_column(String(32), nullable=False, default="Api")

    # Request metadata
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(250), nullable=True)
    path: Mapped[str | None] = mapped_column(String(512), nullable=True)

    # Timestamp
    date_created: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )

    # Processing status (for event-driven job scheduling)
    # These fields are specific to project-level events and not in .NET Event model
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    date_processed: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_error: Mapped[str | None] = mapped_column(Text, nullable=True)


# =============================================================================
# Job Models
# =============================================================================


class Job(Base):
    """
    Job definition stored in project-scoped SQLite.

    Table: jobs
    Purpose: Defines scheduled or event-triggered jobs for a project.

    Note: These are project-specific Python jobs managed via the the API.
    Host-platform C# jobs remain outside the local project database.
    """

    __tablename__ = "jobs"
    __table_args__ = {"schema": "project"}

    # Primary key
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)

    # Core fields
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(String(4000), nullable=True)
    type: Mapped[str] = mapped_column(
        String(500), nullable=False, index=True
    )  # e.g., "python.jobs.ResourceSchemaProfilingJob"
    schedule: Mapped[str | None] = mapped_column(String(100), nullable=True)  # CRON expression
    parameters: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string

    # Execution settings
    timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=300)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    retry_strategy: Mapped[str] = mapped_column(
        String(50), nullable=False, default="None"
    )  # JobRetryStrategy enum
    retry_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=3)

    # Owner
    owner_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)

    # Project association (IProjectEntity) - stored even in project-scoped DBs so
    # future migrations to a shared DB can filter easily by project without
    # relying on the filesystem layout. Added to support project-level queries
    # that include project_id for performance and future Postgres migration.
    project_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)

    # Audit fields
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=utc_now
    )
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    runs: Mapped[list["JobRun"]] = relationship("JobRun", back_populates="job", lazy="dynamic")
    triggers: Mapped[list["JobTrigger"]] = relationship(
        "JobTrigger", back_populates="job", lazy="dynamic"
    )


class JobRun(Base):
    """
    Job execution record stored in project-scoped SQLite.

    Table: job_runs
    Purpose: Tracks each execution of a job with status, progress, and results.
    """

    __tablename__ = "job_runs"
    __table_args__ = {"schema": "project"}

    # Primary key
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)

    # Parent job
    job_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("project.jobs.id"), nullable=False, index=True
    )

    # Optional trigger reference
    trigger_id: Mapped[UUID | None] = mapped_column(
        Uuid, ForeignKey("project.job_triggers.id"), nullable=True, index=True
    )

    # Execution state
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="Queued", index=True
    )  # JobRunStatus enum
    progress: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0-100

    # Timing
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Runtime data
    parameters: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON runtime parameters
    execution_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Queue message ID
    worker: Mapped[str | None] = mapped_column(
        String(256), nullable=True
    )  # Worker process identifier
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Claim lease (the local analogue of a queue visibility timeout): stamped
    # when a worker claims the run and renewed while it executes. The reaper
    # reclaims runs whose lease lapsed (crashed worker) back to Queued, or
    # dead-letters them after the reclaim cap. Null = no live lease.
    lease_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # Results
    result_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    result_data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON result
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_stack: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=utc_now
    )

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="runs")
    trigger: Mapped["JobTrigger | None"] = relationship("JobTrigger", back_populates="runs")
    logs: Mapped[list["JobRunLog"]] = relationship(
        "JobRunLog", back_populates="job_run", lazy="dynamic"
    )
    execution_context: Mapped["ExecutionRunContext | None"] = relationship(
        "ExecutionRunContext", back_populates="job_run", uselist=False
    )


class ExecutionRunContext(Base):
    """
    Durable execution-run context for interactive and resumable platform runs.

    Table: execution_run_contexts
    Purpose: Stores runtime linkage and pause/resume state that should outlive
    transient API processes and in-memory agent state.
    """

    __tablename__ = "execution_run_contexts"
    __table_args__ = {"schema": "project"}

    run_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("project.job_runs.id"), primary_key=True)
    chat_session_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    agent_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    agent_runtime_run_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_run_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    root_run_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True, index=True)
    waiting_for_input: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="0", index=True
    )
    engine_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    engine_metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=utc_now
    )

    job_run: Mapped["JobRun"] = relationship("JobRun", back_populates="execution_context")


class JobTrigger(Base):
    """
    Job trigger configuration stored in project-scoped SQLite.

    Table: job_triggers
    Purpose: Defines when and how a job should be triggered (CRON, event, etc.).
    """

    __tablename__ = "job_triggers"
    __table_args__ = {"schema": "project"}

    # Primary key
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)

    # Parent job
    job_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("project.jobs.id"), nullable=False, index=True
    )

    # Trigger configuration
    trigger_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default=JobTriggerType.SCHEDULED.value, index=True
    )  # JobTriggerType enum
    configuration: Mapped[str] = mapped_column(Text, nullable=False)  # JSON trigger config
    triggered_by_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    triggered_by_id: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Pause state
    is_paused: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Scheduling tracking
    last_scheduled_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Audit fields
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    job: Mapped["Job"] = relationship("Job", back_populates="triggers")
    runs: Mapped[list["JobRun"]] = relationship("JobRun", back_populates="trigger", lazy="dynamic")


class JobRunLog(Base):
    """
    Job run log entry stored in project-scoped SQLite.

    Table: job_run_logs
    Purpose: Stores log messages from job execution for debugging and monitoring.
    """

    __tablename__ = "job_run_logs"
    __table_args__ = {"schema": "project"}

    # Primary key
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)

    # Parent job run
    job_run_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("project.job_runs.id"), nullable=False, index=True
    )

    # Log entry - use Python's utc_now for millisecond precision (SQLite's
    # func.now() only provides second precision, causing log ordering issues)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    level: Mapped[str] = mapped_column(
        String(20), nullable=False, default="Information"
    )  # LogLevel enum
    message: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON additional data

    # Relationships
    job_run: Mapped["JobRun"] = relationship("JobRun", back_populates="logs")


# =============================================================================
# Harness run-state models (neutral SessionPersistence storage; see
# kontext-agent.persistence — harness adapters stay stateless, these tables are
# the platform-owned store swapped in place of harness-owned databases)
# =============================================================================


class AgentRunMessage(Base):
    """Persisted conversation message for a chat session (wire-shape JSON).

    Table: agent_run_messages. The snapshot model keeps writes idempotent:
    after each terminal event the adapter replaces the session's rows with the
    authoritative conversation (never per-delta writes).
    """

    __tablename__ = "agent_run_messages"
    __table_args__ = (
        Index("ix_agent_run_messages_session_seq", "session_id", "seq"),
        {"schema": "project"},
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    seq: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    message_json: Mapped[str] = mapped_column(Text, nullable=False)


class AgentHarnessState(Base):
    """Harness-internal per-session payload (opaque JSON), platform-stored.

    Table: agent_harness_states. Harness adapters serialize private session
    mechanics here so they never own a database/schema of their own; the
    platform stores the blob without interpreting it.
    """

    __tablename__ = "agent_harness_states"
    __table_args__ = {"schema": "project"}

    session_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    state_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=utc_now, onupdate=utc_now
    )
