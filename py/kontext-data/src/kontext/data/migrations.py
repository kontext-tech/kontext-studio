"""Programmatic migration runner for the local SQLite database.

``run_local_migrations()`` is designed for a single-process local install.
It calls ``Base.metadata.create_all()`` which is idempotent — existing tables
are left untouched and only missing tables are created.  This covers the
common upgrade case of adding entirely new tables (like ``local_model_connections``).

Hosted deployments with a shared relational backend are a documented extension
point (see ``RuntimeProfile``); add a migration path for them behind that seam
rather than shipping one here.

Local-only tables (managed only by ``create_all``):
  - local_profile
  - local_preferences
  - local_password_resets
  - local_model_connections
"""

import json
import logging

from sqlalchemy import text

logger = logging.getLogger(__name__)


def run_local_migrations(database_url: str) -> None:
    """Initialise or upgrade a local SQLite database.

    Strategy
    --------
    ``Base.metadata.create_all()`` is idempotent: it creates missing tables
    and leaves existing ones untouched.  This is sufficient for the most
    common upgrade scenario (adding a new table).

    All SQLAlchemy models that are registered with ``Base`` at the time this
    function is called will be reflected — both project tables and local
    identity tables (``local_profile``, ``local_model_connections``, etc.).

    For column-level changes, extend ``_upgrade_local_sqlite_schema`` below
    with SQLite-compatible ``ALTER TABLE`` statements.

    Args:
        database_url: SQLite URL, e.g. ``sqlite:////home/user/.kontext/kontext.db``
    """
    from kontext.data.database import Base

    logger.info("Initialising local SQLite database: %s", database_url)

    from sqlalchemy import create_engine
    from sqlalchemy.pool import NullPool

    engine = create_engine(
        database_url,
        poolclass=NullPool,
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"project": None}},
    )

    try:
        Base.metadata.create_all(engine)
        _upgrade_local_sqlite_schema(engine)
        logger.info("Local database schema is up to date.")
    except Exception as e:
        logger.error("Failed to initialise local database: %s", e, exc_info=True)
        raise
    finally:
        engine.dispose()


def _upgrade_local_sqlite_schema(engine) -> None:
    """Apply lightweight in-place SQLite upgrades for legacy local tables."""
    with engine.begin() as conn:
        _sanitize_sqlite_project_configurations(conn)
        _drop_sqlite_projects_region_code(conn)
        _drop_sqlite_job_triggers_triggered_by(conn)
        _drop_sqlite_agent_skill_schema(conn)

        local_profile_columns = _get_sqlite_table_columns(conn, "local_profile")
        if local_profile_columns:
            _ensure_sqlite_column(
                conn,
                table_name="local_profile",
                column_name="password_hash",
                column_sql="password_hash VARCHAR",
            )
            _ensure_sqlite_column(
                conn,
                table_name="local_profile",
                column_name="preferred_language_code",
                column_sql="preferred_language_code VARCHAR NOT NULL DEFAULT 'en'",
            )
            _ensure_sqlite_column(
                conn,
                table_name="local_profile",
                column_name="email_confirmed",
                column_sql="email_confirmed BOOLEAN NOT NULL DEFAULT 1",
            )

        chat_session_columns = _get_sqlite_table_columns(conn, "chat_sessions")
        if chat_session_columns:
            _ensure_sqlite_column(
                conn,
                table_name="chat_sessions",
                column_name="model_selection_id",
                column_sql="model_selection_id VARCHAR(255)",
            )
            _ensure_sqlite_column(
                conn,
                table_name="chat_sessions",
                column_name="resolved_model_config",
                column_sql="resolved_model_config JSON",
            )
            _ensure_sqlite_column(
                conn,
                table_name="chat_sessions",
                column_name="default_catalog_connection_id",
                column_sql="default_catalog_connection_id UUID",
            )
            _ensure_sqlite_column(
                conn,
                table_name="chat_sessions",
                column_name="default_namespace",
                column_sql="default_namespace VARCHAR(255)",
            )
            _ensure_sqlite_column(
                conn,
                table_name="chat_sessions",
                column_name="default_entity_id",
                column_sql="default_entity_id UUID",
            )
            _ensure_sqlite_column(
                conn,
                table_name="chat_sessions",
                column_name="python_execution_approval_mode",
                column_sql=(
                    "python_execution_approval_mode VARCHAR(32) NOT NULL DEFAULT 'always_ask'"
                ),
            )
        files_columns = _get_sqlite_table_columns(conn, "files")
        if files_columns:
            _ensure_sqlite_column(
                conn,
                table_name="files",
                column_name="provenance",
                column_sql="provenance TEXT",
            )
        query_session_columns = _get_sqlite_table_columns(conn, "query_sessions")
        if query_session_columns:
            _ensure_sqlite_column(
                conn,
                table_name="query_sessions",
                column_name="catalog_connection_id",
                column_sql="catalog_connection_id UUID",
            )
            _ensure_sqlite_column(
                conn,
                table_name="query_sessions",
                column_name="default_namespace",
                column_sql="default_namespace VARCHAR(255)",
            )
            _ensure_sqlite_column(
                conn,
                table_name="query_sessions",
                column_name="default_entity_id",
                column_sql="default_entity_id UUID",
            )
            _ensure_sqlite_column(
                conn,
                table_name="query_sessions",
                column_name="catalog_revision",
                column_sql="catalog_revision VARCHAR(64)",
            )
            _ensure_sqlite_index(
                conn,
                index_name="ix_query_sessions_catalog_connection_id",
                table_name="query_sessions",
                columns=["catalog_connection_id"],
            )
            _ensure_sqlite_index(
                conn,
                index_name="ix_query_sessions_default_entity_id",
                table_name="query_sessions",
                columns=["default_entity_id"],
            )

        job_run_columns = _get_sqlite_table_columns(conn, "job_runs")
        if job_run_columns:
            _ensure_sqlite_column(
                conn,
                table_name="job_runs",
                column_name="lease_expires_at",
                column_sql="lease_expires_at DATETIME",
            )
            _ensure_sqlite_index(
                conn,
                index_name="ix_job_runs_lease_expires_at",
                table_name="job_runs",
                columns=["lease_expires_at"],
            )

        job_trigger_columns = _get_sqlite_table_columns(conn, "job_triggers")
        if job_trigger_columns:
            _ensure_sqlite_column(
                conn,
                table_name="job_triggers",
                column_name="triggered_by_type",
                column_sql="triggered_by_type VARCHAR(50)",
            )
            _ensure_sqlite_column(
                conn,
                table_name="job_triggers",
                column_name="triggered_by_id",
                column_sql="triggered_by_id VARCHAR(255)",
            )

        catalog_connection_columns = _get_sqlite_table_columns(conn, "catalog_connections")
        if catalog_connection_columns:
            _ensure_sqlite_column(
                conn,
                table_name="catalog_connections",
                column_name="source_category",
                column_sql="source_category VARCHAR(32)",
            )
            _ensure_sqlite_column(
                conn,
                table_name="catalog_connections",
                column_name="auth_type",
                column_sql="auth_type VARCHAR(64)",
            )
            _ensure_sqlite_column(
                conn,
                table_name="catalog_connections",
                column_name="execution_mode",
                column_sql="execution_mode VARCHAR(64)",
            )
            _ensure_sqlite_column(
                conn,
                table_name="catalog_connections",
                column_name="health_status",
                column_sql="health_status VARCHAR(64)",
            )
            _ensure_sqlite_column(
                conn,
                table_name="catalog_connections",
                column_name="last_validated_at",
                column_sql="last_validated_at DATETIME",
            )
            _ensure_sqlite_column(
                conn,
                table_name="catalog_connections",
                column_name="validation_error",
                column_sql="validation_error VARCHAR(4096)",
            )
            _ensure_sqlite_column(
                conn,
                table_name="catalog_connections",
                column_name="sync_mode",
                column_sql="sync_mode VARCHAR(64)",
            )
            _ensure_sqlite_column(
                conn,
                table_name="catalog_connections",
                column_name="sync_schedule",
                column_sql="sync_schedule VARCHAR(256)",
            )
            _ensure_sqlite_column(
                conn,
                table_name="catalog_connections",
                column_name="catalog_revision",
                column_sql="catalog_revision VARCHAR(64)",
            )

        local_connection_columns = _get_sqlite_table_columns(conn, "local_model_connections")
        if local_connection_columns:
            _ensure_sqlite_column(
                conn,
                table_name="local_model_connections",
                column_name="secret_value",
                column_sql="secret_value VARCHAR(2048)",
            )
            _ensure_sqlite_column(
                conn,
                table_name="local_model_connections",
                column_name="secret_values_json",
                column_sql="secret_values_json TEXT",
            )
            _ensure_sqlite_column(
                conn,
                table_name="local_model_connections",
                column_name="connection_config_json",
                column_sql="connection_config_json TEXT",
            )
            _ensure_sqlite_column(
                conn,
                table_name="local_model_connections",
                column_name="default_sampling_json",
                column_sql="default_sampling_json TEXT",
            )
            _ensure_sqlite_column(
                conn,
                table_name="local_model_connections",
                column_name="secret_configured",
                column_sql="secret_configured BOOLEAN NOT NULL DEFAULT 0",
            )
            _ensure_sqlite_column(
                conn,
                table_name="local_model_connections",
                column_name="enabled",
                column_sql="enabled BOOLEAN NOT NULL DEFAULT 1",
            )
            _ensure_sqlite_column(
                conn,
                table_name="local_model_connections",
                column_name="validation_state",
                column_sql="validation_state VARCHAR(32) NOT NULL DEFAULT 'unknown'",
            )
            _backfill_local_model_connection_json_columns(
                conn, _get_sqlite_table_columns(conn, "local_model_connections")
            )

        file_columns = _get_sqlite_table_columns(conn, "files")
        if file_columns:
            _ensure_sqlite_column(
                conn,
                table_name="files",
                column_name="prefix",
                column_sql="prefix VARCHAR(1024) NOT NULL DEFAULT ''",
            )
            conn.execute(text('UPDATE "files" SET "prefix" = "" WHERE "prefix" IS NULL'))
            _ensure_sqlite_index(
                conn,
                index_name="ix_project_files_project_id_prefix_name",
                table_name="files",
                columns=["project_id", "prefix", "name"],
            )


def _get_sqlite_table_columns(conn, table_name: str) -> set[str]:
    rows = conn.execute(text(f'PRAGMA table_info("{table_name}")')).mappings().all()
    return {str(row["name"]) for row in rows}


def _drop_sqlite_projects_region_code(conn) -> None:
    """Drop the legacy ``projects.region_code`` column from local SQLite DBs."""
    columns = _get_sqlite_table_columns(conn, "projects")
    if "region_code" not in columns:
        return

    conn.execute(text('ALTER TABLE "projects" DROP COLUMN "region_code"'))
    logger.info("Dropped legacy SQLite column projects.region_code")


def _drop_sqlite_job_triggers_triggered_by(conn) -> None:
    """Drop the legacy ``job_triggers.triggered_by`` label column.

    Trigger actors are now stored as ``triggered_by_type``/``triggered_by_id``;
    the free-form label column is no longer read or written.
    """
    columns = _get_sqlite_table_columns(conn, "job_triggers")
    if "triggered_by" not in columns:
        return

    conn.execute(text('ALTER TABLE "job_triggers" DROP COLUMN "triggered_by"'))
    logger.info("Dropped legacy SQLite column job_triggers.triggered_by")


def _drop_sqlite_agent_skill_schema(conn) -> None:
    """Drop the retired agent-skill tables and the chat-session pin column.

    Skills were removed end to end; drop the remaining local SQLite artifacts so
    the database matches the current model set. ``chat_sessions.skill_version_id``
    participates in a foreign key, and SQLite refuses ``ALTER TABLE ... DROP
    COLUMN`` for such columns, so the column is removed through SQLite's
    documented table-rebuild procedure instead.
    """
    if "skill_version_id" in _get_sqlite_table_columns(conn, "chat_sessions"):
        _rebuild_sqlite_table(conn, "chat_sessions", drop_columns={"skill_version_id"})
        logger.info("Rebuilt legacy SQLite table chat_sessions without skill_version_id")

    conn.execute(text('DROP TABLE IF EXISTS "agent_skill_versions"'))
    conn.execute(text('DROP TABLE IF EXISTS "agent_skills"'))


def _rebuild_sqlite_table(conn, table_name: str, *, drop_columns: set[str]) -> None:
    """Recreate a SQLite table without ``drop_columns`` and copy its rows over.

    ``ALTER TABLE ... DROP COLUMN`` cannot remove a column referenced by a
    foreign-key constraint, so fall back to the standard create-copy-swap
    procedure. ``chat_sessions`` only ever had a foreign key on the dropped
    column, so rebuilding without foreign-key clauses is lossless here; surviving
    indexes are recreated from their original definitions.
    """
    columns = conn.execute(text(f'PRAGMA table_info("{table_name}")')).mappings().all()
    kept = [row for row in columns if str(row["name"]) not in drop_columns]
    if not kept or len(kept) == len(columns):
        return

    definitions: list[str] = []
    for row in kept:
        definition = f'"{row["name"]}" {str(row["type"] or "").strip()}'.rstrip()
        if row["notnull"] or row["pk"]:
            definition += " NOT NULL"
        if row["pk"]:
            definition += " PRIMARY KEY"
        if row["dflt_value"] is not None:
            definition += f" DEFAULT {row['dflt_value']}"
        definitions.append(definition)

    index_rows = (
        conn.execute(
            text(
                "SELECT name, sql FROM sqlite_master "
                "WHERE type = 'index' AND tbl_name = :table AND sql IS NOT NULL"
            ),
            {"table": table_name},
        )
        .mappings()
        .all()
    )
    kept_indexes = [
        str(index["sql"])
        for index in index_rows
        if not any(str(column) in str(index["sql"]) for column in drop_columns)
    ]

    new_table = f"{table_name}__rebuild"
    column_list = ", ".join(f'"{row["name"]}"' for row in kept)
    conn.execute(text(f'DROP TABLE IF EXISTS "{new_table}"'))
    conn.execute(text(f'CREATE TABLE "{new_table}" ({", ".join(definitions)})'))
    conn.execute(
        text(f'INSERT INTO "{new_table}" ({column_list}) SELECT {column_list} FROM "{table_name}"')
    )
    conn.execute(text(f'DROP TABLE "{table_name}"'))
    conn.execute(text(f'ALTER TABLE "{new_table}" RENAME TO "{table_name}"'))
    for index_sql in kept_indexes:
        conn.execute(text(index_sql))


def _ensure_sqlite_column(conn, *, table_name: str, column_name: str, column_sql: str) -> None:
    columns = _get_sqlite_table_columns(conn, table_name)
    if column_name in columns:
        return

    conn.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN {column_sql}'))
    logger.info("Added missing SQLite column %s.%s", table_name, column_name)


def _ensure_sqlite_index(conn, *, index_name: str, table_name: str, columns: list[str]) -> None:
    quoted_columns = ", ".join(f'"{column}"' for column in columns)
    conn.execute(
        text(f'CREATE INDEX IF NOT EXISTS "{index_name}" ON "{table_name}" ({quoted_columns})')
    )


def _backfill_local_model_connection_json_columns(conn, columns: set[str]) -> None:
    updates: list[tuple[str, str, str, str]] = []

    if "connection_config_json" in columns:
        config_parts: list[str] = []
        if "provider_model_name" in columns:
            config_parts.append("'providerModelName', provider_model_name")
        if "endpoint_base_url" in columns:
            config_parts.append("'endpointBaseUrl', endpoint_base_url")
        if "secret_ref" in columns:
            config_parts.append("'secretRef', secret_ref")

        if config_parts:
            updates.append(
                (
                    "connection_config_json",
                    f"json_object({', '.join(config_parts)})",
                    "connection_config_json IS NULL",
                    " OR ".join(
                        f"{legacy_column} IS NOT NULL"
                        for legacy_column in (
                            "provider_model_name",
                            "endpoint_base_url",
                            "secret_ref",
                        )
                        if legacy_column in columns
                    ),
                )
            )

    if "default_sampling_json" in columns and "default_sampling" in columns:
        updates.append(
            (
                "default_sampling_json",
                "",
                "default_sampling_json IS NULL",
                "default_sampling IS NOT NULL",
            )
        )

    for target_column, value_sql, empty_predicate, source_predicate in updates:
        if not source_predicate:
            continue

        if target_column == "default_sampling_json":
            rows = conn.execute(
                text(
                    'SELECT id, default_sampling FROM "local_model_connections" '
                    "WHERE default_sampling_json IS NULL AND default_sampling IS NOT NULL"
                )
            ).mappings()
            for row in rows:
                raw_value = row["default_sampling"]
                if raw_value is None:
                    continue
                if isinstance(raw_value, str):
                    try:
                        json.loads(raw_value)
                        serialized = raw_value
                    except json.JSONDecodeError:
                        serialized = json.dumps(raw_value)
                else:
                    serialized = json.dumps(raw_value)
                conn.execute(
                    text(
                        'UPDATE "local_model_connections" '
                        "SET default_sampling_json = :serialized "
                        "WHERE id = :id"
                    ),
                    {"id": row["id"], "serialized": serialized},
                )
            continue

        conn.execute(
            text(
                'UPDATE "local_model_connections" '
                f"SET {target_column} = {value_sql} "
                f"WHERE {empty_predicate} AND ({source_predicate})"
            )
        )


def _sanitize_sqlite_project_configurations(conn) -> None:
    """Strip removed legacy keys from persisted project configuration blobs."""
    project_columns = _get_sqlite_table_columns(conn, "projects")
    if "configuration" not in project_columns:
        return

    rows = conn.execute(
        text('SELECT id, configuration FROM "projects" WHERE configuration IS NOT NULL')
    ).mappings()

    legacy_keys = {
        "allowed_model_selection_ids",
        "allowedModelSelectionIds",
        "allowed_llm_model_ids",
        "allowedLlmModelIds",
        "is_local",
        "isLocal",
    }

    for row in rows:
        raw_config = row["configuration"]
        if raw_config is None:
            continue

        if isinstance(raw_config, str):
            try:
                config = json.loads(raw_config)
            except json.JSONDecodeError:
                continue
        elif isinstance(raw_config, dict):
            config = dict(raw_config)
        else:
            continue

        if not isinstance(config, dict):
            continue

        cleaned_config = {key: value for key, value in config.items() if key not in legacy_keys}
        if cleaned_config == config:
            continue

        conn.execute(
            text('UPDATE "projects" SET configuration = :configuration WHERE id = :id'),
            {
                "id": row["id"],
                "configuration": json.dumps(cleaned_config),
            },
        )
