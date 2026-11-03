"""Helpers for normalizing persisted project configuration."""

from __future__ import annotations

from collections.abc import Iterable

from kontext.schema import (
    FileFormatType,
    FileTypeConfiguration,
    ProjectConfiguration,
    ProjectFeature,
)

_PLATFORM_REQUIRED_FILE_TYPES: tuple[
    tuple[FileTypeConfiguration, tuple[ProjectFeature, ...]],
    ...,
] = (
    (
        FileTypeConfiguration(
            file_extension=".kontext",
            file_format_type=FileFormatType.NOTEBOOK,
            allowed_content_types=[
                "application/json",
                "text/json",
                "application/octet-stream",
            ],
        ),
        (),
    ),
    (
        FileTypeConfiguration(
            file_extension=".dt",
            file_format_type=FileFormatType.DATATABLE,
            allowed_content_types=[
                "application/json",
                "text/json",
                "application/octet-stream",
            ],
        ),
        (ProjectFeature.DATALAKE,),
    ),
    (
        FileTypeConfiguration(
            file_extension=".chart",
            file_format_type=FileFormatType.CHART,
            allowed_content_types=[
                "application/json",
                "text/json",
                "application/octet-stream",
            ],
        ),
        (ProjectFeature.DATALAKE,),
    ),
)


def normalize_project_configuration(
    configuration: ProjectConfiguration | None,
) -> ProjectConfiguration | None:
    """Backfill platform-managed file types into persisted project config.

    We intentionally keep this narrow. Persisted configs may represent an
    explicit user restriction, so we only re-add the platform-managed artifact
    types that internal workflows rely on.
    """
    if configuration is None:
        return None

    features = list(configuration.features or [])
    allowed_file_types = [
        file_type.model_copy(deep=True) for file_type in configuration.allowed_file_types or []
    ]
    feature_set = set(features)

    for required_file_type, required_features in _PLATFORM_REQUIRED_FILE_TYPES:
        if required_features and not set(required_features).issubset(feature_set):
            continue
        if _contains_file_type(allowed_file_types, required_file_type):
            continue
        allowed_file_types.append(required_file_type.model_copy(deep=True))

    return ProjectConfiguration(
        allowed_file_types=allowed_file_types,
        max_file_bytes_size=configuration.max_file_bytes_size,
        total_storage_allocation_bytes=configuration.total_storage_allocation_bytes,
        features=features,
        default_query_engine=configuration.default_query_engine,
    )


def _contains_file_type(
    allowed_file_types: Iterable[FileTypeConfiguration],
    candidate: FileTypeConfiguration,
) -> bool:
    return any(
        file_type.file_extension.lower() == candidate.file_extension.lower()
        and file_type.file_format_type == candidate.file_format_type
        for file_type in allowed_file_types
    )
