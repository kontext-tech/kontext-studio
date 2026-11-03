"""Local-mode project helpers and CRUD operations."""

from __future__ import annotations

import logging
import uuid
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import func, select

from kontext.account import UserProfile, read_profile
from kontext.common import ConflictError, NotFoundError
from kontext.common.pagination import total_pages as common_total_pages
from kontext.common.utils.datetime_utils import normalize_datetime_utc, utc_now
from kontext.data.database import get_sync_db_session
from kontext.data.models import Project
from kontext.data.project_configuration import normalize_project_configuration
from kontext.schema import (
    AccessLevel,
    CreateProjectRequest,
    FileFormatType,
    FileTypeConfiguration,
    PaginatedListOfProjectModel,
    ProjectConfiguration,
    ProjectFeature,
    ProjectModel,
    QueryEngineType,
    UpdateProjectRequest,
)

logger = logging.getLogger(__name__)

LOCAL_PROJECT_CODE = "local"
LOCAL_PROJECT_NAME = "Local Project"
LOCAL_PROJECT_DESCRIPTION = "Default local project created automatically."
LOCAL_PROJECT_ACCESS_LEVEL = AccessLevel.PRIVATE


def get_default_local_file_types() -> list[FileTypeConfiguration]:
    """Return the default set of supported local project file types.

    This is the single source of truth for the local project configuration;
    `kontext.runtime.local.config` re-exports it rather than duplicating it.
    """
    return [
        FileTypeConfiguration(
            file_extension=".md",
            file_format_type=FileFormatType.MARKDOWN,
            allowed_content_types=["text/markdown", "text/plain"],
        ),
        FileTypeConfiguration(
            file_extension=".png",
            file_format_type=FileFormatType.IMAGE,
            allowed_content_types=["image/png"],
        ),
        FileTypeConfiguration(
            file_extension=".jpg",
            file_format_type=FileFormatType.IMAGE,
            allowed_content_types=["image/jpeg"],
        ),
        FileTypeConfiguration(
            file_extension=".jpeg",
            file_format_type=FileFormatType.IMAGE,
            allowed_content_types=["image/jpeg"],
        ),
        FileTypeConfiguration(
            file_extension=".gif",
            file_format_type=FileFormatType.IMAGE,
            allowed_content_types=["image/gif"],
        ),
        FileTypeConfiguration(
            file_extension=".webp",
            file_format_type=FileFormatType.IMAGE,
            allowed_content_types=["image/webp"],
        ),
        FileTypeConfiguration(
            file_extension=".drawio",
            file_format_type=FileFormatType.DRAWIO,
            allowed_content_types=["application/vnd.jgraph.mxfile"],
        ),
        FileTypeConfiguration(
            file_extension=".kontext",
            file_format_type=FileFormatType.NOTEBOOK,
            allowed_content_types=[
                "application/json",
                "text/json",
                "application/octet-stream",
            ],
        ),
        FileTypeConfiguration(
            file_extension=".csv",
            file_format_type=FileFormatType.CSV,
            allowed_content_types=["text/csv", "application/csv"],
        ),
        FileTypeConfiguration(
            file_extension=".tsv",
            file_format_type=FileFormatType.TSV,
            allowed_content_types=["text/tab-separated-values"],
        ),
        FileTypeConfiguration(
            file_extension=".json",
            file_format_type=FileFormatType.JSON,
            allowed_content_types=["application/json", "text/json"],
        ),
        FileTypeConfiguration(
            file_extension=".jsonl",
            file_format_type=FileFormatType.JSONL,
            allowed_content_types=[
                "application/jsonl",
                "application/x-ndjson",
                "application/x-jsonlines",
                "text/jsonl",
            ],
        ),
        FileTypeConfiguration(
            file_extension=".parquet",
            file_format_type=FileFormatType.PARQUET,
            allowed_content_types=["application/octet-stream", "application/parquet"],
        ),
        FileTypeConfiguration(
            file_extension=".xlsx",
            file_format_type=FileFormatType.EXCEL,
            allowed_content_types=[
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "application/octet-stream",
            ],
        ),
        FileTypeConfiguration(
            file_extension=".xls",
            file_format_type=FileFormatType.EXCEL,
            allowed_content_types=[
                "application/vnd.ms-excel",
                "application/octet-stream",
            ],
        ),
        FileTypeConfiguration(
            file_extension=".pdf",
            file_format_type=FileFormatType.PDF,
            allowed_content_types=["application/pdf"],
        ),
        FileTypeConfiguration(
            file_extension=".dt",
            file_format_type=FileFormatType.DATATABLE,
            allowed_content_types=[
                "application/json",
                "text/json",
                "application/octet-stream",
            ],
        ),
        FileTypeConfiguration(
            file_extension=".chart",
            file_format_type=FileFormatType.CHART,
            allowed_content_types=[
                "application/json",
                "text/json",
                "application/octet-stream",
            ],
        ),
        FileTypeConfiguration(
            file_extension=".txt",
            file_format_type=FileFormatType.TEXT,
            allowed_content_types=["text/plain"],
        ),
        FileTypeConfiguration(
            file_extension=".sql",
            file_format_type=FileFormatType.TEXT,
            allowed_content_types=["text/plain", "application/sql"],
        ),
        FileTypeConfiguration(
            file_extension=".yaml",
            file_format_type=FileFormatType.TEXT,
            allowed_content_types=[
                "text/plain",
                "text/yaml",
                "application/yaml",
                "application/x-yaml",
            ],
        ),
        FileTypeConfiguration(
            file_extension=".yml",
            file_format_type=FileFormatType.TEXT,
            allowed_content_types=[
                "text/plain",
                "text/yaml",
                "application/yaml",
                "application/x-yaml",
            ],
        ),
    ]


def get_default_local_project_configuration() -> ProjectConfiguration:
    """Return the default project configuration used in local mode."""
    return ProjectConfiguration(
        allowed_file_types=get_default_local_file_types(),
        max_file_bytes_size=536870912,
        total_storage_allocation_bytes=10737418240,
        features=[
            ProjectFeature.CHAT,
            ProjectFeature.DATALAKE,
            ProjectFeature.SEARCH,
        ],
        default_query_engine=QueryEngineType.DUCKDB,
    )


def get_default_local_project_configuration_payload() -> dict[str, object]:
    """Return the serialized local project configuration for persistence."""
    return get_default_local_project_configuration().model_dump()


def to_project_model(row: Project) -> ProjectModel:
    config: ProjectConfiguration = get_default_local_project_configuration()
    raw_config = row.configuration
    if isinstance(raw_config, dict):
        try:
            parsed_config = ProjectConfiguration.from_dict(raw_config)
            normalized_config = normalize_project_configuration(parsed_config)
            if normalized_config is not None:
                config = normalized_config
        except Exception:
            pass

    return ProjectModel(
        id=str(row.id),
        project_name=row.project_name,
        project_code=row.project_code,
        access_level=AccessLevel(row.access_level or "Private"),
        project_description=row.project_description,
        configuration=config,
        owner_id=str(row.owner_id) if row.owner_id else str(row.id),
        date_created=normalize_datetime_utc(row.date_created),
        modified_by_user_id=(str(row.modified_by_user_id) if row.modified_by_user_id else None),
        date_modified=normalize_datetime_utc(row.date_modified),
        is_deleted=row.is_deleted,
        date_deleted=normalize_datetime_utc(row.date_deleted),
    )


def ensure_lake_dirs(project_id: str) -> None:
    try:
        from kontext.storage.engine.local import LocalStorageEngine

        engine = LocalStorageEngine()
        engine.ensure_project_structure(project_id)
    except Exception as exc:
        logger.warning("Could not create lake dirs for project %s: %s", project_id, exc)


def get_project_by_code_service(code: str) -> ProjectModel:
    with get_sync_db_session() as session:
        row = session.execute(
            select(Project).where(Project.project_code == code, Project.is_deleted.is_(False))
        ).scalar_one_or_none()

    if row is None:
        raise NotFoundError(f"Project with code '{code}' not found.")
    return to_project_model(row)


def get_filtered_projects_service(
    *, page_index: int, page_size: int, filter_string: str | None
) -> PaginatedListOfProjectModel:
    with get_sync_db_session() as session:
        base_query = select(Project).where(Project.is_deleted == False)  # noqa: E712

        if filter_string:
            from sqlalchemy import or_

            q = f"%{filter_string.lower()}%"
            base_query = base_query.where(
                or_(
                    func.lower(Project.project_name).like(q),
                    func.lower(Project.project_code).like(q),
                )
            )

        total = (
            session.execute(select(func.count()).select_from(base_query.subquery())).scalar() or 0
        )
        rows = (
            session.execute(base_query.offset((page_index - 1) * page_size).limit(page_size))
            .scalars()
            .all()
        )

    return PaginatedListOfProjectModel(
        items=[to_project_model(r) for r in rows],
        total_count=total,
        page_index=page_index,
        page_size=page_size,
        total_pages=common_total_pages(total, page_size),
    )


def create_project_service(
    request: CreateProjectRequest, current_user: UserProfile
) -> ProjectModel:
    with get_sync_db_session() as session:
        existing = session.execute(
            select(Project).where(
                Project.project_code == request.project_code,
                Project.is_deleted == False,  # noqa: E712
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise ConflictError(f"Project code '{request.project_code}' already exists.")

        owner_id = UUID(current_user.id)
        project_id = uuid4()
        now = utc_now()
        row = Project(
            id=project_id,
            project_code=request.project_code,
            project_name=request.project_name,
            project_description=request.project_description,
            access_level=LOCAL_PROJECT_ACCESS_LEVEL.value,
            configuration=get_default_local_project_configuration_payload(),
            owner_id=owner_id,
            date_created=now,
            is_deleted=False,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        result = to_project_model(row)

    ensure_lake_dirs(str(project_id))
    return result


def get_project_service(project_id: str) -> ProjectModel:
    with get_sync_db_session() as session:
        row = session.execute(
            select(Project).where(Project.id == UUID(project_id))
        ).scalar_one_or_none()

    if row is None:
        raise NotFoundError("Project not found.")
    return to_project_model(row)


def update_project_service(
    project_id: str, request: UpdateProjectRequest, current_user: UserProfile
) -> ProjectModel:
    with get_sync_db_session() as session:
        row = session.execute(
            select(Project).where(Project.id == UUID(project_id))
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Project not found.")

        row.project_name = request.project_name
        if request.project_description is not None:
            row.project_description = request.project_description
        row.modified_by_user_id = UUID(current_user.id)
        row.date_modified = utc_now()

        session.commit()
        session.refresh(row)
        return to_project_model(row)


def delete_project_service(project_id: str) -> dict[str, str]:
    with get_sync_db_session() as session:
        row = session.execute(
            select(Project).where(Project.id == UUID(project_id))
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("Project not found.")

        row.is_deleted = True
        row.date_deleted = utc_now()
        session.commit()

    return {"detail": "Project deleted."}


def seed_default_local_project() -> None:
    """Create or repair the default local project.

    Single source of truth for both the API and the local runtime bootstrap.
    Existing rows are repaired rather than replaced, and the default feature
    list is merged with any features the user has already enabled.
    """
    from sqlalchemy.exc import IntegrityError

    with get_sync_db_session() as session:
        now = utc_now()
        existing_project = session.execute(
            select(Project).where(
                Project.project_code == LOCAL_PROJECT_CODE,
                Project.is_deleted.is_(False),
            )
        ).scalar_one_or_none()

        profile = read_profile()
        raw_owner_id = profile.id if profile else str(uuid4())
        owner_id = (
            uuid.UUID(str(raw_owner_id))
            if not isinstance(raw_owner_id, uuid.UUID)
            else raw_owner_id
        )

        if existing_project is not None:
            repaired_existing_project = False
            default_config = get_default_local_project_configuration_payload()
            if existing_project.owner_id != owner_id:
                existing_project.owner_id = owner_id
                repaired_existing_project = True
            if existing_project.date_created is None:
                existing_project.date_created = now
                repaired_existing_project = True
            existing_config = (
                existing_project.configuration
                if isinstance(existing_project.configuration, dict)
                else {}
            )
            merged_config = {**default_config, **existing_config}
            existing_features = cast(list[str], existing_config.get("features") or [])
            merged_config["features"] = list(
                dict.fromkeys([*cast(list[str], default_config["features"]), *existing_features])
            )
            if merged_config != existing_config:
                existing_project.configuration = merged_config
                repaired_existing_project = True
            if repaired_existing_project:
                session.commit()
                logger.info("Repaired default local project metadata for %s.", owner_id)
            return

        project_id = uuid4()
        project_record = Project(
            id=project_id,
            project_code=LOCAL_PROJECT_CODE,
            project_name=LOCAL_PROJECT_NAME,
            project_description=LOCAL_PROJECT_DESCRIPTION,
            access_level=LOCAL_PROJECT_ACCESS_LEVEL.value,
            configuration=get_default_local_project_configuration_payload(),
            owner_id=owner_id,
            date_created=now,
        )

        session.add(project_record)
        try:
            session.commit()
        except IntegrityError:
            # A concurrent boot inserted the default project first.
            session.rollback()
            logger.info("Default local project was seeded concurrently; continuing.")
            return

    logger.info("Seeded default local project (id=%s) into SQLite database.", project_id)
