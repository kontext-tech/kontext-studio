import json
import sqlite3

from kontext.data.migrations import run_local_migrations


def test_run_local_migrations_adds_lakehouse_scope_columns(tmp_path) -> None:
    db_path = tmp_path / "legacy-local.db"
    connection = sqlite3.connect(db_path)

    try:
        connection.execute(
            """
            CREATE TABLE chat_sessions (
                id CHAR(32) NOT NULL PRIMARY KEY,
                project_id CHAR(32),
                session_name VARCHAR(512),
                model_selection_id VARCHAR(255),
                resolved_model_config JSON,
                skill_version_id CHAR(32),
                agent_type VARCHAR(32) NOT NULL DEFAULT 'team',
                query_session_id CHAR(32),
                engine_type VARCHAR(50),
                python_execution_approval_mode VARCHAR(32) NOT NULL DEFAULT 'always_ask',
                tokens_inbound BIGINT,
                tokens_outbound BIGINT,
                created_by VARCHAR(255),
                created_at DATETIME NOT NULL,
                updated_by VARCHAR(255),
                updated_at DATETIME,
                is_deleted BOOLEAN NOT NULL,
                deleted_at DATETIME,
                owner_id CHAR(32),
                FOREIGN KEY(skill_version_id) REFERENCES agent_skill_versions (id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE query_sessions (
                id TEXT PRIMARY KEY,
                session_name TEXT,
                project_id TEXT NOT NULL,
                default_dataset_id TEXT,
                owner_id TEXT,
                status TEXT,
                engine_type TEXT,
                job_run_id TEXT,
                database_size_bytes INTEGER,
                metadata_json TEXT,
                created_by TEXT,
                created_at TEXT,
                updated_by TEXT,
                updated_at TEXT,
                last_accessed_at TEXT,
                is_deleted INTEGER,
                deleted_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                project_code TEXT,
                project_name TEXT,
                region_code TEXT,
                owner_id TEXT,
                access_level TEXT,
                used_storage_bytes INTEGER,
                date_created TEXT,
                modified_by_user_id TEXT,
                date_modified TEXT,
                is_deleted INTEGER,
                date_deleted TEXT,
                last_synced_at TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE agent_skills (
                id TEXT PRIMARY KEY,
                project_id TEXT,
                skill_name TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE agent_skill_versions (
                id TEXT PRIMARY KEY,
                skill_id TEXT,
                version_number INTEGER
            )
            """
        )
        connection.execute("CREATE INDEX ix_chat_sessions_project_id ON chat_sessions (project_id)")
        connection.execute(
            "INSERT INTO chat_sessions (id, project_id, session_name, created_at, is_deleted) "
            "VALUES ('aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa', 'p1', 'Legacy session', '2024-01-01', 0)"
        )
        connection.commit()
    finally:
        connection.close()

    run_local_migrations(f"sqlite:///{db_path}")

    upgraded_connection = sqlite3.connect(db_path)
    try:
        chat_session_columns = {
            str(row[1]) for row in upgraded_connection.execute('PRAGMA table_info("chat_sessions")')
        }
        query_session_columns = {
            str(row[1])
            for row in upgraded_connection.execute('PRAGMA table_info("query_sessions")')
        }
        project_columns = {
            str(row[1]) for row in upgraded_connection.execute('PRAGMA table_info("projects")')
        }
        table_names = {
            str(row[0])
            for row in upgraded_connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        chat_session_indexes = {
            str(row[0])
            for row in upgraded_connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='chat_sessions'"
            )
        }

        assert "region_code" not in project_columns
        assert "default_catalog_connection_id" in chat_session_columns
        assert "default_namespace" in chat_session_columns
        assert "default_entity_id" in chat_session_columns
        assert "python_execution_approval_mode" in chat_session_columns
        assert "skill_version_id" not in chat_session_columns
        assert "agent_skills" not in table_names
        assert "agent_skill_versions" not in table_names
        # The constraint-safe rebuild must preserve surviving indexes and rows.
        assert "ix_chat_sessions_project_id" in chat_session_indexes
        assert "ix_chat_sessions_skill_version_id" not in chat_session_indexes
        assert upgraded_connection.execute(
            "SELECT project_id, session_name, is_deleted FROM chat_sessions "
            "WHERE id = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'"
        ).fetchone() == ("p1", "Legacy session", 0)
        assert "catalog_connection_id" in query_session_columns
        assert "default_namespace" in query_session_columns
        assert "default_entity_id" in query_session_columns
        assert "catalog_revision" in query_session_columns
        approval_mode = upgraded_connection.execute(
            'SELECT python_execution_approval_mode FROM "chat_sessions" LIMIT 1'
        ).fetchone()
        assert approval_mode is None or approval_mode[0] == "always_ask"
    finally:
        upgraded_connection.close()


def test_run_local_migrations_sanitizes_legacy_project_configuration(tmp_path) -> None:
    db_path = tmp_path / "legacy-project-config.db"
    connection = sqlite3.connect(db_path)

    try:
        connection.execute(
            """
            CREATE TABLE projects (
                id TEXT PRIMARY KEY,
                project_code TEXT,
                project_name TEXT,
                configuration TEXT,
                region_code TEXT,
                owner_id TEXT,
                access_level TEXT,
                used_storage_bytes INTEGER,
                date_created TEXT,
                modified_by_user_id TEXT,
                date_modified TEXT,
                is_deleted INTEGER,
                date_deleted TEXT,
                last_synced_at TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO projects (
                id,
                project_code,
                project_name,
                configuration,
                region_code,
                owner_id,
                access_level,
                used_storage_bytes,
                is_deleted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "project-1",
                "local",
                "Local Project",
                (
                    '{"allowedFileTypes":[],"maxFileBytesSize":1,'
                    '"totalStorageAllocationBytes":2,"features":[],'
                    '"allowedModelSelectionIds":["m1"],'
                    '"allowed_llm_model_ids":["m2"],'
                    '"isLocal":true}'
                ),
                "local",
                "owner-1",
                "Private",
                0,
                0,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    run_local_migrations(f"sqlite:///{db_path}")

    upgraded_connection = sqlite3.connect(db_path)
    try:
        raw_configuration = upgraded_connection.execute(
            'SELECT configuration FROM "projects" WHERE id = "project-1"'
        ).fetchone()[0]
        configuration = json.loads(raw_configuration)
        assert "allowedModelSelectionIds" not in configuration
        assert "allowed_llm_model_ids" not in configuration
        assert "isLocal" not in configuration
        assert configuration["features"] == []
    finally:
        upgraded_connection.close()


def test_run_local_migrations_adds_local_model_connection_secret_values_json(
    tmp_path,
) -> None:
    db_path = tmp_path / "legacy-model-connections.db"
    connection = sqlite3.connect(db_path)

    try:
        connection.execute(
            """
            CREATE TABLE local_model_connections (
                id TEXT PRIMARY KEY,
                source_type TEXT NOT NULL,
                adapter_type TEXT NOT NULL,
                connection_kind TEXT NOT NULL,
                canonical_model_id TEXT NOT NULL,
                display_name TEXT NOT NULL,
                secret_value TEXT,
                secret_configured INTEGER NOT NULL DEFAULT 0,
                is_default INTEGER NOT NULL DEFAULT 0,
                enabled INTEGER NOT NULL DEFAULT 1,
                validation_state TEXT NOT NULL DEFAULT 'unknown'
            )
            """
        )
        connection.commit()
    finally:
        connection.close()

    run_local_migrations(f"sqlite:///{db_path}")

    upgraded_connection = sqlite3.connect(db_path)
    try:
        columns = {
            str(row[1])
            for row in upgraded_connection.execute('PRAGMA table_info("local_model_connections")')
        }

        assert "secret_values_json" in columns
        assert "connection_config_json" in columns
        assert "default_sampling_json" in columns
    finally:
        upgraded_connection.close()


def test_run_local_migrations_adds_file_prefix_column(tmp_path) -> None:
    db_path = tmp_path / "legacy-files.db"
    connection = sqlite3.connect(db_path)

    try:
        connection.execute(
            """
            CREATE TABLE files (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                uri TEXT,
                file_type TEXT NOT NULL,
                content_type TEXT,
                size INTEGER NOT NULL,
                project_id TEXT,
                is_deleted INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.execute(
            """
            INSERT INTO files (
                id,
                name,
                uri,
                file_type,
                content_type,
                size,
                project_id,
                is_deleted
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "file-1",
                "orders.csv",
                "file:///tmp/orders.csv",
                "CSV",
                "text/csv",
                12,
                "project-1",
                0,
            ),
        )
        connection.commit()
    finally:
        connection.close()

    run_local_migrations(f"sqlite:///{db_path}")

    upgraded_connection = sqlite3.connect(db_path)
    try:
        columns = {str(row[1]) for row in upgraded_connection.execute('PRAGMA table_info("files")')}
        assert "prefix" in columns
        prefix_value = upgraded_connection.execute(
            'SELECT prefix FROM "files" WHERE id = "file-1"'
        ).fetchone()
        assert prefix_value == ("",)
    finally:
        upgraded_connection.close()


def test_run_local_migrations_replaces_job_trigger_actor_label_column(tmp_path) -> None:
    db_path = tmp_path / "legacy-job-triggers.db"
    connection = sqlite3.connect(db_path)

    try:
        connection.execute(
            """
            CREATE TABLE job_triggers (
                id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                trigger_type TEXT NOT NULL,
                configuration TEXT NOT NULL,
                triggered_by TEXT
            )
            """
        )
        connection.execute(
            """
            INSERT INTO job_triggers (id, job_id, trigger_type, configuration, triggered_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("trigger-1", "job-1", "Manual", "{}", "User:legacy"),
        )
        connection.commit()
    finally:
        connection.close()

    run_local_migrations(f"sqlite:///{db_path}")

    upgraded_connection = sqlite3.connect(db_path)
    try:
        columns = {
            str(row[1]) for row in upgraded_connection.execute('PRAGMA table_info("job_triggers")')
        }
        assert "triggered_by" not in columns
        assert "triggered_by_type" in columns
        assert "triggered_by_id" in columns
    finally:
        upgraded_connection.close()


def test_run_local_migrations_adds_files_provenance_column(tmp_path) -> None:
    db_path = tmp_path / "legacy-files-provenance.db"
    connection = sqlite3.connect(db_path)

    try:
        connection.execute(
            """
            CREATE TABLE files (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                file_type TEXT NOT NULL,
                size INTEGER NOT NULL,
                project_id TEXT,
                is_deleted INTEGER NOT NULL DEFAULT 0
            )
            """
        )
        connection.execute(
            """
            INSERT INTO files (id, name, file_type, size, project_id, is_deleted)
            VALUES ('file-1', 'orders.csv', 'CSV', 12, 'project-1', 0)
            """
        )
        connection.commit()
    finally:
        connection.close()

    run_local_migrations(f"sqlite:///{db_path}")

    upgraded_connection = sqlite3.connect(db_path)
    try:
        columns = {str(row[1]) for row in upgraded_connection.execute('PRAGMA table_info("files")')}
        assert "provenance" in columns
        row = upgraded_connection.execute(
            'SELECT provenance FROM "files" WHERE id = "file-1"'
        ).fetchone()
        assert row == (None,)
    finally:
        upgraded_connection.close()
