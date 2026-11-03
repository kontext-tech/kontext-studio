"""Local-mode persistence helpers for auth and project context loading."""

from __future__ import annotations

import uuid
from uuid import UUID

from sqlalchemy import select

from kontext.data.database import get_sync_db_session
from kontext.data.models import Project
from kontext.schema import ProjectModel

from .local import to_project_model


def get_local_project_roles_for_user(user_id: str) -> dict[str, list[str]]:
    """Return project-role assignments for a local user based on ownership."""
    try:
        owner_id = uuid.UUID(str(user_id))
    except Exception:
        return {}

    with get_sync_db_session() as session:
        project_ids = (
            session.execute(
                select(Project.id).where(
                    Project.owner_id == owner_id,
                    Project.is_deleted.is_(False),
                )
            )
            .scalars()
            .all()
        )

    return {str(project_id): ["owner"] for project_id in project_ids}


def load_local_project_model(project_id: UUID) -> ProjectModel | None:
    """Load a local-mode project as a schema model."""
    with get_sync_db_session() as session:
        row = session.execute(select(Project).where(Project.id == project_id)).scalar_one_or_none()

    if row is None:
        return None

    return to_project_model(row)
