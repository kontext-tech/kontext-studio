from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from kontext.data.catalog_service import CatalogDataService, CatalogEntitySnapshot
from kontext.data.database import Base
from kontext.data.models import CatalogConnection as CatalogConnectionRecord
from kontext.data.models import QuerySession
from kontext.schema import (
    CatalogColumn,
    CatalogConnectionKind,
    CatalogEntityType,
    CatalogSourceKind,
)


def _make_service(tmp_path) -> tuple[CatalogDataService, str, UUID]:
    """Build a CatalogDataService backed by a real in-memory SQLite DB."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"project": None}},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    project_id = str(uuid4())
    service = CatalogDataService(project_id)

    def session_scope(*, commit: bool = True):
        from contextlib import contextmanager

        @contextmanager
        def _scope():
            session = factory()
            try:
                yield session
                if commit:
                    session.commit()
            except Exception:
                session.rollback()
                raise
            finally:
                session.close()

        return _scope()

    service._session_scope = session_scope  # type: ignore[method-assign]

    connection = CatalogConnectionRecord(
        id=uuid4(),
        project_id=UUID(project_id),
        provider_kind=CatalogSourceKind.POSTGRESQLEXTERNAL.value,
        connection_kind=CatalogConnectionKind.EXTERNAL.value,
        display_name="Warehouse",
        enabled=True,
        capabilities_json={},
    )
    connection_id = connection.id
    with factory() as session:
        session.add(connection)
        session.commit()
    return service, project_id, connection_id


def _snapshot(
    name: str, *, column: str = "id", metadata_location: str = "file:///a"
) -> CatalogEntitySnapshot:
    return CatalogEntitySnapshot(
        namespace_name="public",
        entity_name=name,
        entity_type=CatalogEntityType.TABLE,
        metadata={"metadataLocation": metadata_location},
        columns=[CatalogColumn(name=column, data_type="INTEGER")],
    )


def test_snapshot_sync_preserves_entity_ids_across_identical_syncs(tmp_path) -> None:
    service, _project_id, connection_id = _make_service(tmp_path)

    first = service.replace_connection_snapshot(connection_id, [_snapshot("orders")])
    entities_after_first = service.list_entities(connection_id=str(connection_id))
    second = service.replace_connection_snapshot(connection_id, [_snapshot("orders")])
    entities_after_second = service.list_entities(connection_id=str(connection_id))

    assert first.catalog_revision == second.catalog_revision
    assert [entity.id for entity in entities_after_first] == [
        entity.id for entity in entities_after_second
    ]


def test_snapshot_sync_removes_deleted_entities_and_keeps_the_rest(tmp_path) -> None:
    service, _project_id, connection_id = _make_service(tmp_path)

    service.replace_connection_snapshot(
        connection_id, [_snapshot("orders"), _snapshot("customers")]
    )
    before = {
        entity.entity_name: entity.id
        for entity in service.list_entities(connection_id=str(connection_id))
    }

    service.replace_connection_snapshot(connection_id, [_snapshot("orders")])
    after = {
        entity.entity_name: entity.id
        for entity in service.list_entities(connection_id=str(connection_id))
    }

    assert set(after) == {"orders"}
    assert after["orders"] == before["orders"]


def test_snapshot_sync_revision_changes_when_metadata_location_changes(tmp_path) -> None:
    service, _project_id, connection_id = _make_service(tmp_path)

    first = service.replace_connection_snapshot(connection_id, [_snapshot("orders")])
    second = service.replace_connection_snapshot(
        connection_id, [_snapshot("orders", metadata_location="file:///b")]
    )

    assert first.catalog_revision != second.catalog_revision


def test_query_session_catalog_revision_round_trips(tmp_path) -> None:
    from contextlib import contextmanager

    from kontext.data.query_session_service import QuerySessionDataService

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"project": None}},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    project_id = str(uuid4())
    service = QuerySessionDataService(project_id)

    @contextmanager
    def session_scope(*, commit: bool = True):
        session = factory()
        try:
            yield session
            if commit:
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    service._session_scope = session_scope  # type: ignore[method-assign]

    session_id = uuid4()
    with factory() as session:
        session.add(
            QuerySession(
                id=session_id,
                session_name="Session",
                project_id=UUID(project_id),
                is_deleted=False,
            )
        )
        session.commit()

    assert service.set_catalog_revision(str(session_id), "rev-1") is True
    assert service.get_catalog_revision(connection_id=None) is None
    fetched = service.get_session(str(session_id))
    assert fetched is not None
    assert fetched.catalog_revision == "rev-1"
