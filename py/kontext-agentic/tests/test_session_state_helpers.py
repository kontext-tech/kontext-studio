from kontext.agent import (
    KONTEXT_SESSION_ARTIFACT_ALIASES_KEY,
    KONTEXT_SESSION_ARTIFACTS_KEY,
    KONTEXT_SESSION_ATTACHED_DATA_SOURCES_KEY,
    KONTEXT_SESSION_DATA_IDENTITY_INDEX_KEY,
    KONTEXT_SESSION_NAMESPACE,
    SharedSessionStore,
    build_data_identity_key,
    create_kontext_session_state,
)
from kontext.schema import (
    ArtifactType,
    AttachedDataSource,
    FileFormatType,
)


def test_shared_session_store_upserts_artifact_descriptors_by_id() -> None:
    session_state = create_kontext_session_state()
    store = SharedSessionStore(session_state)

    store.upsert_artifact_descriptor(
        artifact_id="file-123",
        artifact_type=ArtifactType.DATATABLE,
        title="Transactions",
        sql="select * from transactions",
        identity_key=build_data_identity_key("select * from transactions"),
        row_count=100,
        column_names=["id", "amount"],
    )
    store.upsert_artifact_descriptor(
        artifact_id="file-123",
        artifact_type=ArtifactType.DATATABLE,
        title="Transactions v2",
    )

    descriptor = store.get_artifact_descriptor("file-123")

    assert descriptor is not None
    assert descriptor.title == "Transactions v2"
    assert descriptor.sql == "select * from transactions"
    assert descriptor.row_count == 100
    assert list(session_state[KONTEXT_SESSION_NAMESPACE][KONTEXT_SESSION_ARTIFACTS_KEY]) == [
        "file-123"
    ]


def test_shared_session_store_resolves_latest_data_artifact_by_identity() -> None:
    session_state = create_kontext_session_state()
    store = SharedSessionStore(session_state)
    identity_key = build_data_identity_key("select * from transactions")

    store.upsert_artifact_descriptor(
        artifact_id="file-old",
        artifact_type=ArtifactType.DATATABLE,
        sql="select * from transactions",
        identity_key=identity_key,
    )
    store.upsert_artifact_descriptor(
        artifact_id="file-new",
        artifact_type=ArtifactType.DATATABLE,
        sql="select * from transactions",
        identity_key=identity_key,
    )

    descriptor = store.find_data_artifact_by_identity(identity_key)

    assert descriptor is not None
    assert descriptor.artifact_id == "file-new"
    assert (
        session_state[KONTEXT_SESSION_NAMESPACE][KONTEXT_SESSION_DATA_IDENTITY_INDEX_KEY][
            identity_key
        ]
        == "file-new"
    )


def test_shared_session_store_resolves_promoted_aliases() -> None:
    session_state = create_kontext_session_state()
    store = SharedSessionStore(session_state)

    store.upsert_artifact_descriptor(
        artifact_id="file-123",
        artifact_type=ArtifactType.DATATABLE,
        title="Transactions",
    )
    store.register_artifact_alias("temp-123", "file-123")

    descriptor = store.get_artifact_descriptor("temp-123")

    assert descriptor is not None
    assert descriptor.artifact_id == "file-123"
    assert (
        session_state[KONTEXT_SESSION_NAMESPACE][KONTEXT_SESSION_ARTIFACT_ALIASES_KEY]["temp-123"]
        == "file-123"
    )


def test_shared_session_store_seeds_attached_data_sources_at_creation() -> None:
    file_id = "c2cd7ac7-9453-4709-94de-50e088e8d0e6"
    session_state = create_kontext_session_state(
        [
            AttachedDataSource(
                file_id=file_id,
                file_name="Financial Sample.xlsx",
                file_type=FileFormatType.EXCEL,
                tables=[],
            )
        ]
    )

    assert (
        session_state[KONTEXT_SESSION_NAMESPACE][KONTEXT_SESSION_ATTACHED_DATA_SOURCES_KEY][0][
            "file_id"
        ]
        == file_id
    )


def test_build_data_identity_key_normalizes_enum_and_scope_forms() -> None:
    """Typed and raw scope values must hash identically across surfaces."""
    from uuid import uuid4

    from kontext.schema import QueryEngineType

    base = build_data_identity_key("select * from transactions", engine_type="DuckDB")
    assert base == build_data_identity_key(
        "select * from transactions", engine_type=QueryEngineType.DUCKDB
    )

    scope_id = uuid4()
    assert build_data_identity_key("SELECT 1", catalog_connection_id=scope_id) == (
        build_data_identity_key("SELECT 1", catalog_connection_id=str(scope_id))
    )

    assert build_data_identity_key("select    *\nfrom t") == build_data_identity_key(
        "select * from t"
    )
