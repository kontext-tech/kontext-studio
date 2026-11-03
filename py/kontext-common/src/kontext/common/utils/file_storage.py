"""
File storage utilities for managing file paths and storage configuration.

This module provides common utilities for file storage path management across
different parts of Kontext, ensuring consistent path handling
and storage configuration.
"""

import os
from pathlib import Path

from .path_policy import ensure_within_allowed_roots

ROOT_PROJECT_FILE_PREFIX = ""
NOTEBOOK_PROJECT_FILE_PREFIX = ".notebooks"
CHART_PROJECT_FILE_PREFIX = ".charts"
DATATABLE_PROJECT_FILE_PREFIX = ".dts"
RESULT_STORE_PROJECT_FILE_PREFIX = ".data"
LAKEHOUSE_PROJECT_FILE_PREFIX = ".lakehouse"
KNOWLEDGE_PROJECT_FILE_PREFIX = ".knowledge"
OKF_PROJECT_FILE_PREFIX = ".okf"
SYSTEM_MANAGED_PROJECT_FILE_PREFIXES = frozenset(
    {
        LAKEHOUSE_PROJECT_FILE_PREFIX,
        KNOWLEDGE_PROJECT_FILE_PREFIX,
        OKF_PROJECT_FILE_PREFIX,
    }
)


def normalize_project_file_prefix(prefix: str | None) -> str:
    """Normalize a logical file prefix to a stable relative POSIX path."""
    if prefix is None:
        return ROOT_PROJECT_FILE_PREFIX

    normalized = prefix.strip().replace("\\", "/")
    if normalized in {"", ".", "/"}:
        return ROOT_PROJECT_FILE_PREFIX

    parts: list[str] = []
    for part in normalized.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            raise ValueError("File prefix cannot traverse parent directories")
        parts.append(part)

    return "/".join(parts)


def split_project_file_path(name: str, prefix: str | None = None) -> tuple[str, str]:
    """Split a logical file path into normalized prefix and leaf filename."""
    normalized_prefix = normalize_project_file_prefix(prefix)
    normalized_name = name.strip().replace("\\", "/")
    if not normalized_name:
        raise ValueError("File name cannot be empty")

    parts: list[str] = []
    for part in normalized_name.split("/"):
        if part in {"", "."}:
            continue
        if part == "..":
            raise ValueError("File name cannot traverse parent directories")
        parts.append(part)

    if not parts:
        raise ValueError("File name cannot be empty")

    leaf_name = parts[-1]
    inferred_prefix = "/".join(parts[:-1])
    combined_prefix = normalize_project_file_prefix(
        "/".join(filter(None, [normalized_prefix, inferred_prefix]))
    )
    return combined_prefix, leaf_name


def build_project_file_path(name: str, prefix: str | None = None) -> str:
    """Build a normalized logical file path from a leaf name and optional prefix."""
    normalized_prefix, leaf_name = split_project_file_path(name, prefix)
    if not normalized_prefix:
        return leaf_name
    return f"{normalized_prefix}/{leaf_name}"


def is_system_managed_project_file_prefix(prefix: str | None) -> bool:
    """Return whether the prefix belongs to a reserved system-managed subtree."""
    normalized_prefix = normalize_project_file_prefix(prefix)
    if not normalized_prefix:
        return False
    root_prefix = normalized_prefix.split("/", 1)[0]
    return root_prefix in SYSTEM_MANAGED_PROJECT_FILE_PREFIXES


def get_file_storage_path() -> str:
    """
    Get the base file storage path for database and session files.

    This function checks the FILE_STORAGE_PATH environment variable first,
    and falls back to the shared ``~/.kontext/storage`` directory used by
    other local runtime components if not configured.

    Returns:
        str: The absolute path to the file storage directory
    """
    file_storage_path = os.getenv("FILE_STORAGE_PATH")
    if not file_storage_path:
        file_storage_path = str(Path.home() / ".kontext" / "storage")

    file_storage_path = str(Path(file_storage_path).expanduser())

    # Ensure the directory exists
    os.makedirs(file_storage_path, exist_ok=True)

    return file_storage_path


def get_project_storage_path(project_id: str, *sub_paths: str) -> str:
    """
    Get a project-specific storage path.

    Args:
        project_id: The project identifier
        sub_paths: Optional sub-paths within the project directory

    Returns:
        str: The absolute path to the project storage directory
    """
    base_path = Path(get_file_storage_path()) / "projects" / project_id
    final_path = base_path.joinpath(*sub_paths) if sub_paths else base_path

    # Confine project storage to the managed storage root. A project id or
    # sub-path containing ".." (or an absolute segment) would otherwise escape
    # the storage tree, so canonicalize and reject before touching the disk.
    final_path = ensure_within_allowed_roots(final_path)

    # Ensure the directory exists
    final_path.parent.mkdir(parents=True, exist_ok=True)

    return str(final_path)


def get_project_vector_db_path(project_id: str, engine_type: str = "lancedb") -> str:
    """
    Get the path for a project's vector database.

    Args:
        project_id: The project identifier
        engine_type: The vector engine type (default: lancedb)

    Returns:
        str: The absolute path to the vector DB directory
    """
    return get_project_storage_path(project_id, "vector", engine_type)
