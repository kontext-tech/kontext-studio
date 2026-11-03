from __future__ import annotations

from dataclasses import dataclass, field

from kontext.common.catalog.revision import compute_catalog_revision
from kontext.common.query.session_compatibility import is_session_compatible
from kontext.schema import QueryEngineType, QuerySessionModel, QuerySessionStatus


@dataclass
class _Entity:
    namespace_name: str
    entity_name: str
    entity_type: str = "Table"
    location: str | None = None
    columns: list = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    @property
    def name(self) -> str:
        return self.entity_name


def test_compute_catalog_revision_is_order_independent() -> None:
    a = _Entity("bronze", "orders", columns=[{"name": "id", "data_type": "INTEGER"}])
    b = _Entity("bronze", "customers", columns=[{"name": "id", "data_type": "INTEGER"}])

    assert compute_catalog_revision([a, b]) == compute_catalog_revision([b, a])


def test_compute_catalog_revision_changes_with_metadata_location() -> None:
    base = _Entity("bronze", "orders", metadata={"metadataLocation": "file:///a"})
    changed = _Entity("bronze", "orders", metadata={"metadataLocation": "file:///b"})

    assert compute_catalog_revision([base]) != compute_catalog_revision([changed])


def test_compute_catalog_revision_ignores_cosmetic_metadata() -> None:
    base = _Entity("bronze", "orders", metadata={"metadataLocation": "file:///a"})
    cosmetic = _Entity(
        "bronze", "orders", metadata={"metadataLocation": "file:///a", "rowCount": 99}
    )

    assert compute_catalog_revision([base]) == compute_catalog_revision([cosmetic])


def _session(revision: str | None) -> QuerySessionModel:
    return QuerySessionModel.model_construct(
        id="c5dcdeff-aba0-43e0-95a4-b60074a01381",
        session_name="Session",
        project_id="c1658a20-3558-4f89-b719-9573ef5e271b",
        status=QuerySessionStatus.ACTIVE,
        engine_type=QueryEngineType.DUCKDB,
        catalog_revision=revision,
    )


def test_session_incompatible_when_catalog_revision_differs() -> None:
    assert not is_session_compatible(
        _session("old-revision"), expected_catalog_revision="new-revision"
    )


def test_session_compatible_when_catalog_revision_matches() -> None:
    assert is_session_compatible(
        _session("same-revision"), expected_catalog_revision="same-revision"
    )


def test_session_compatible_when_revision_unknown() -> None:
    # Legacy sessions without a persisted revision remain reusable; the engine
    # reconciles their views on reuse.
    assert is_session_compatible(_session(None), expected_catalog_revision="new-revision")
    assert is_session_compatible(_session("old"), expected_catalog_revision=None)
