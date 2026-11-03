from __future__ import annotations

from pathlib import Path


def test_active_python_surface_has_no_legacy_dataset_or_chroma_terms() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    active_source_files = sorted((repo_root / "py").glob("*/src/**/*.py"))
    banned_terms = [
        "dataset",
        "default_dataset_id",
        "include_dataset_listing_tools",
        "index_dataset",
        "chromadefaultembedding",
    ]

    matches: list[str] = []
    for path in active_source_files:
        if "/alembic/" in path.as_posix():
            continue
        if "/py/kontext-schema/src/kontext/schema/" in f"/{path.as_posix()}":
            continue
        source = path.read_text(encoding="utf-8").lower()
        for term in banned_terms:
            if term in source:
                matches.append(f"{path.relative_to(repo_root)}: {term}")

    assert matches == []


def test_zod_schema_pipeline_has_no_legacy_dataset_models() -> None:
    repo_root = Path(__file__).resolve().parents[3]

    assert not (repo_root / "ts/schema/src/data-lake/datasets.ts").exists()

    source_files = [
        repo_root / "ts/schema/src/data-lake/index.ts",
        repo_root / "ts/schema/src/index.ts",
        repo_root / "ts/schema/scripts/export-schemas.mjs",
        repo_root / "ts/schema/src/data-lake/files.ts",
    ]
    banned_terms = [
        "DatasetModelSchema",
        "DatasetNavModelSchema",
        "CreateDatasetRequestSchema",
        "CreateSystemDatasetRequestSchema",
        "UpdateDatasetRequestSchema",
        "DatasetObjectSchemaDefinitionSchema",
        "DatasetObjectModelSchema",
        "DatasetObjectNavModelSchema",
        "DatasetObjectWithFilesModelSchema",
        "DatasetFileModelSchema",
        "DatasetFileNavModelSchema",
        "DatasetFileWithFileModelSchema",
        "CreateDatasetFileRequestSchema",
        "UpdateDatasetFileRequestSchema",
        "DatasetTreeNodeModelSchema",
        "DatasetObjectTreeNodeModelSchema",
        "DatasetLiteTreeNodeModelSchema",
        "DatasetObjectLiteModelSchema",
        "DatasetFileLiteModelSchema",
        "DatasetTreeResponseSchema",
        "PaginatedDatasetResponseSchema",
        "PaginatedDatasetObjectResponseSchema",
        "DatasetFileGroupResponseSchema",
        "ProjectStorageStatsModelSchema",
        "DataZoneSchema",
        "DatasetObjectTypeSchema",
        "DatasetSourceTypeSchema",
    ]

    matches: list[str] = []
    for path in source_files:
        source = path.read_text(encoding="utf-8")
        for term in banned_terms:
            if term in source:
                matches.append(f"{path.relative_to(repo_root)}: {term}")

    assert matches == []


def test_catalog_event_surface_uses_catalog_entity_events() -> None:
    repo_root = Path(__file__).resolve().parents[3]

    source_expectations = {
        repo_root / "ts/schema/src/core/domains/events/types.ts": {
            "required": [
                "CreateCatalogEntity",
                "UpdateCatalogEntity",
                "DeleteCatalogEntity",
            ],
            "banned": [
                "CreateDataset",
                "UpdateDataset",
                "DeleteDataset",
                "CreateDatasetObject",
                "UpdateDatasetObject",
                "DeleteDatasetObject",
            ],
        },
        repo_root / "ts/schema/src/enumMappings.ts": {
            "required": [
                "CreateCatalogEntity",
                "UpdateCatalogEntity",
                "DeleteCatalogEntity",
            ],
            "banned": [
                "CreateDataset",
                "UpdateDataset",
                "DeleteDataset",
                "CreateDatasetObject",
                "UpdateDatasetObject",
                "DeleteDatasetObject",
            ],
        },
        repo_root / "ts/event/src/components/EventIcons.tsx": {
            "required": [
                "EventType.CreateCatalogEntity",
                "EventType.UpdateCatalogEntity",
                "EventType.DeleteCatalogEntity",
            ],
            "banned": [
                "EventType.CreateDataset",
                "EventType.UpdateDataset",
                "EventType.DeleteDataset",
                "EventType.CreateDatasetObject",
                "EventType.UpdateDatasetObject",
                "EventType.DeleteDatasetObject",
            ],
        },
        repo_root / "ts/event/src/utils/eventTypeUtils.ts": {
            "required": [
                "EventType.CreateCatalogEntity",
                "EventType.UpdateCatalogEntity",
                "EventType.DeleteCatalogEntity",
            ],
            "banned": [
                "EventType.CreateDataset",
                "EventType.UpdateDataset",
                "EventType.DeleteDataset",
                "EventType.CreateDatasetObject",
                "EventType.UpdateDatasetObject",
                "EventType.DeleteDatasetObject",
            ],
        },
        repo_root / "backend/Kontext.Events/Services/IEventActivityService.cs": {
            "required": [],
            "banned": [
                "RecordCatalogEntityCreatedAsync",
                "RecordCatalogEntityUpdatedAsync",
                "RecordCatalogEntityDeletedAsync",
                "RecordDatasetObjectCreationAsync",
                "RecordDatasetObjectUpdateAsync",
                "RecordDatasetObjectDeletionAsync",
            ],
        },
        repo_root / "backend/Kontext.Events/Services/EventActivityService.cs": {
            "required": [],
            "banned": [
                "RecordCatalogEntityCreated",
                "RecordCatalogEntityUpdated",
                "RecordCatalogEntityDeleted",
                "EventType.CreateCatalogEntity",
                "EventType.UpdateCatalogEntity",
                "EventType.DeleteCatalogEntity",
                "CatalogEntityCreatedEventData",
                "CatalogEntityUpdatedEventData",
                "CatalogEntityDeletedEventData",
                "EventType.CreateDatasetObject",
                "EventType.UpdateDatasetObject",
                "EventType.DeleteDatasetObject",
                "DatasetObjectCreationEventData",
                "DatasetObjectUpdateEventData",
                "DatasetObjectDeletionEventData",
            ],
        },
        repo_root / "backend/Kontext.Schema/_generated/EventType.cs": {
            "required": [
                "CreateCatalogEntity",
                "UpdateCatalogEntity",
                "DeleteCatalogEntity",
            ],
            "banned": [
                "CreateDataset",
                "UpdateDataset",
                "DeleteDataset",
                "CreateDatasetObject",
                "UpdateDatasetObject",
                "DeleteDatasetObject",
            ],
        },
        repo_root / "py/kontext-schema/src/kontext/schema/event_type.py": {
            "required": [
                "CREATECATALOGENTITY",
                "UPDATECATALOGENTITY",
                "DELETECATALOGENTITY",
            ],
            "banned": [
                "CREATEDATASET",
                "UPDATEDATASET",
                "DELETEDATASET",
                "CREATEDATASETOBJECT",
                "UPDATEDATASETOBJECT",
                "DELETEDATASETOBJECT",
            ],
        },
    }

    for path, expectations in source_expectations.items():
        if not path.exists():
            continue
        source = path.read_text(encoding="utf-8")
        for term in expectations["required"]:
            assert term in source, f"{term} missing from {path.relative_to(repo_root)}"
        for term in expectations["banned"]:
            assert term not in source, f"{term} still present in {path.relative_to(repo_root)}"

    assert not (repo_root / "backend/Kontext.Events/Data/DatasetObjectEventData.cs").exists()
