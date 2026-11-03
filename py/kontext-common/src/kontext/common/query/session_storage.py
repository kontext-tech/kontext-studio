"""Storage-path helpers for persisted query sessions.

These live in ``kontext-common`` so both the query orchestration layer and the
in-process engine adapter can resolve session database paths without importing
each other. The functions only depend on the shared project-storage helper.
"""

import logging
from pathlib import Path

from kontext.common.utils.file_storage import get_project_storage_path

logger = logging.getLogger(__name__)


def get_session_database_path(
    project_id: str, session_id: str, persistent: bool = True
) -> str | None:
    """
    Get the full path to a session's database file.

    For persistent sessions, the database file is stored in:
    {file_storage_path}/projects/{project_id}/sessions/{session_id}.db

    Args:
        project_id: The project ID (will be normalized to lowercase)
        session_id: The session ID
        persistent: Whether this is a persistent session. Returns None for
            in-memory sessions.

    Returns:
        str: Path to the database file for persistent sessions,
        None for in-memory sessions
    """
    if not persistent:
        return None

    project_dir = Path(get_project_storage_path(project_id.lower(), "sessions"))
    project_dir.mkdir(parents=True, exist_ok=True)

    # Database file: {session_id}.db
    db_file = project_dir / f"{session_id}.db"
    return str(db_file)


def get_project_sessions_directory(project_id: str) -> str:
    """
    Get the directory path where all sessions for a project are stored.

    Args:
        project_id: The project ID (will be normalized to lowercase)

    Returns:
        str: Path to the project's sessions directory
    """
    return get_project_storage_path(project_id.lower(), "sessions")


def ensure_session_directory_exists(project_id: str) -> str:
    """
    Ensure the session directory exists for a project and return its path.

    Args:
        project_id: The project ID

    Returns:
        str: Path to the project's sessions directory
    """
    project_dir = get_project_sessions_directory(project_id)
    Path(project_dir).mkdir(parents=True, exist_ok=True)
    return project_dir


def delete_session_database_file(project_id: str, session_id: str) -> bool:
    """
    Delete a session's database file from disk.

    This function safely removes the DuckDB database file for a session.
    It handles cases where the file doesn't exist (already deleted or
    in-memory session) gracefully.

    Args:
        project_id: The project ID
        session_id: The session ID

    Returns:
        True if the file was deleted, False if it didn't exist
    """
    db_path = get_session_database_path(project_id, session_id, persistent=True)

    if not db_path:
        logger.debug(f"No database path for session {session_id} (in-memory session)")
        return False

    db_file = Path(db_path)

    if not db_file.exists():
        logger.debug(f"Database file does not exist: {db_path}")
        return False

    try:
        file_size = db_file.stat().st_size
        db_file.unlink()
        logger.info(f"Deleted session database file: {db_path} ({file_size} bytes freed)")
        return True
    except OSError as e:
        logger.warning(f"Failed to delete session database file {db_path}: {e}")
        return False
