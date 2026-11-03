from kontext.data.project_configuration import normalize_project_configuration
from kontext.schema import (
    FileFormatType,
    FileTypeConfiguration,
    ProjectConfiguration,
    ProjectFeature,
    QueryEngineType,
)


def _file_type(file_extension: str, file_format_type: FileFormatType):
    return FileTypeConfiguration(
        file_extension=file_extension,
        file_format_type=file_format_type,
        allowed_content_types=["application/octet-stream"],
    )


def test_normalize_project_configuration_backfills_platform_artifacts_for_datalake():
    configuration = ProjectConfiguration(
        allowed_file_types=[_file_type(".csv", FileFormatType.CSV)],
        max_file_bytes_size=1024,
        total_storage_allocation_bytes=2048,
        features=[ProjectFeature.CHAT, ProjectFeature.DATALAKE],
        default_query_engine=QueryEngineType.DUCKDB,
    )

    normalized = normalize_project_configuration(configuration)

    assert normalized is not None
    normalized_extensions = {
        file_type.file_extension for file_type in normalized.allowed_file_types
    }
    assert normalized_extensions == {".csv", ".kontext", ".dt", ".chart"}
    assert ".jsonl" not in normalized_extensions


def test_normalize_project_configuration_only_backfills_notebook_without_datalake():
    configuration = ProjectConfiguration(
        allowed_file_types=[_file_type(".md", FileFormatType.MARKDOWN)],
        max_file_bytes_size=1024,
        total_storage_allocation_bytes=2048,
        features=[ProjectFeature.CHAT],
        default_query_engine=QueryEngineType.DUCKDB,
    )

    normalized = normalize_project_configuration(configuration)

    assert normalized is not None
    normalized_extensions = {
        file_type.file_extension for file_type in normalized.allowed_file_types
    }
    assert normalized_extensions == {".md", ".kontext"}
