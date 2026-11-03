from __future__ import annotations

import asyncio
from contextlib import contextmanager
from typing import TYPE_CHECKING, TypeVar
from uuid import UUID

from sqlalchemy.orm import Session

from .database import get_sync_session_for_project

if TYPE_CHECKING:
    from kontext.schema import ProjectConfiguration

"""Base data service for consistent session management patterns.

This module provides base classes for data services that manage their own
database sessions internally. This ensures thread-safe session handling
and atomic transactions.

Architecture:
- Services receive a project_id and create sessions internally
- Each operation creates, uses, and closes a session within to_thread()
- Sessions are never passed between threads
- Transactions are atomic and self-contained
"""

# Type variable for entities
T = TypeVar("T")


class ProjectDataService:
    """Base class for project-scoped data services.

    Services manage their own database sessions internally, creating
    them on-demand within asyncio.to_thread() calls to ensure thread-safe
    session handling.

    Example:
        class FileDataService(ProjectDataService):
            async def get_file_async(self, file_id: UUID) -> ProjectFile | None:
                return await asyncio.to_thread(self._get_file_sync, file_id)

            def _get_file_sync(self, file_id: UUID) -> ProjectFile | None:
                with self._session_scope() as session:
                    return session.get(ProjectFile, file_id)
    """

    def __init__(self, project_id: UUID | str, project_name: str | None = None) -> None:
        """Initialize the service with project context.

        Args:
            project_id: The project ID for database session scoping.
            project_name: Optional project name for context
                (e.g., view models, logging).
        """
        self._project_id = str(project_id)
        self._project_name = project_name

    @property
    def project_uuid(self) -> UUID | None:
        """Return the project_id as a UUID instance (or None)."""
        return parse_uuid(self._project_id)

    @contextmanager
    def _session_scope(self, *, commit: bool = True):
        """Context manager for database sessions with automatic commit/rollback.

        Creates a new session, yields it for use, and handles commit/rollback
        automatically. Use this pattern for all database operations.

        Args:
            commit: Whether to commit on success (default True).
                    Set to False for read-only operations.

        Yields:
            SQLAlchemy Session instance

        Raises:
            Any exception raised within the context (after rollback)
        """
        session = get_sync_session_for_project(self._project_id)
        try:
            yield session
            if commit:
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def _make_detached(self, session: Session, entity: T) -> T:
        """Make an entity safe to use outside the session context.

        Refreshes the entity to load all attributes, then expunges it from
        the session so it can be safely used after the session closes.

        Use this for entities that will be returned from methods and used
        outside the session context.

        Args:
            session: The active SQLAlchemy session.
            entity: The entity to detach.

        Returns:
            The same entity, now detached from the session.
        """
        session.refresh(entity)
        session.expunge(entity)
        return entity

    def _get_project_config(self, session: Session) -> ProjectConfiguration | None:
        """Get the project configuration from the database.

        Args:
            session: SQLAlchemy Session instance

        Returns:
            Project configuration model if found, else None.
        """
        from sqlalchemy import select

        from kontext.schema import ProjectConfiguration

        from .models import Project
        from .project_configuration import normalize_project_configuration

        stmt = select(Project).where(
            Project.id == UUID(self._project_id),
            Project.is_deleted == False,  # noqa: E712
        )
        project = session.execute(stmt).scalar_one_or_none()
        if not project or not project.configuration:
            return None

        return normalize_project_configuration(
            ProjectConfiguration.from_dict(project.configuration)
        )

    async def get_project_config_async(self) -> ProjectConfiguration | None:
        """Get the project configuration (async wrapper)."""
        return await asyncio.to_thread(self.get_project_config)

    def get_project_config(self) -> ProjectConfiguration | None:
        """Get the project configuration."""
        with self._session_scope(commit=False) as session:
            return self._get_project_config(session)

    def _merge_entity(self, session: Session, entity: T) -> T:
        """Merge a detached entity into the current session.

        Use this when you receive a detached entity (from another session)
        and need to use it in the current session context.

        Args:
            session: The active SQLAlchemy session.
            entity: The detached entity to merge.

        Returns:
            The merged entity, now attached to the session.
        """
        return session.merge(entity)


def parse_uuid(value: str | UUID | None) -> UUID | None:
    """Parse a string or UUID to UUID, returning None for None input.

    Args:
        value: String, UUID, or None to parse.

    Returns:
        UUID instance or None.

    Raises:
        ValueError: If the string is not a valid UUID.
    """
    if value is None:
        return None
    if isinstance(value, UUID):
        return value
    return UUID(value)


def ensure_uuid(value: str | UUID) -> UUID:
    """Parse a string or UUID to UUID, raising on None.

    Args:
        value: String or UUID to parse.

    Returns:
        UUID instance.

    Raises:
        ValueError: If the string is not a valid UUID.
    """
    if isinstance(value, UUID):
        return value
    return UUID(value)


def uuid_to_str(value: UUID | str | None) -> str | None:
    """Convert a UUID to string, returning None for None input.

    Args:
        value: UUID, string, or None to convert.

    Returns:
        String representation or None.
    """
    if value is None:
        return None
    return str(value)
