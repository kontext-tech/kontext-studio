"""Filesystem path policy: confine local file access to approved roots.

Kontext components read and write files on the machine that runs them. To keep
that surface small, every local filesystem path that originates outside the
managed storage tree (stored file URIs, external catalog connection config,
CLI arguments) is validated against a set of allowed roots before use.

Roots default to the managed storage directory (``FILE_STORAGE_PATH`` or
``~/.kontext/storage``) and can be extended with ``KONTEXT_ALLOWED_PATHS`` - an
``os.pathsep``-separated list of directories. Everything is canonicalized with
``Path.resolve`` first, so ``..`` traversal and symlinks that escape an allowed
root are rejected.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

from kontext.common.constants.env_vars import StorageEnvVars

# Single source of truth for the escape-hatch variable name; also referenced in
# ``.env.example`` and ``StorageEnvVars``.
ALLOWED_PATHS_ENV = StorageEnvVars.ALLOWED_PATHS


class PathAccessDeniedError(PermissionError):
    """Raised when a path resolves outside every allowed root."""


def _resolve(path: str | os.PathLike[str]) -> Path:
    return Path(path).expanduser().resolve()


def _canonicalize_roots(
    roots: Iterable[str | os.PathLike[str]],
) -> tuple[Path, ...]:
    """Resolve roots (so ``..``/symlinks collapse) and drop duplicates."""
    resolved_roots: list[Path] = []
    for root in roots:
        candidate = _resolve(root)
        if candidate not in resolved_roots:
            resolved_roots.append(candidate)
    return tuple(resolved_roots)


def get_allowed_roots() -> tuple[Path, ...]:
    """Return the canonical directories that local file access is confined to.

    The managed storage directory is always included. ``KONTEXT_ALLOWED_PATHS``
    (``os.pathsep``-separated) adds any additional opt-in roots. The value is
    read on every call so tests and long-running processes can adjust it.
    """
    # Imported lazily: ``file_storage`` imports this module, so importing it at
    # module scope would create a cycle.
    from .file_storage import get_file_storage_path

    roots: list[str | os.PathLike[str]] = [get_file_storage_path()]
    raw = os.getenv(ALLOWED_PATHS_ENV)
    if raw:
        roots.extend(entry for entry in raw.split(os.pathsep) if entry.strip())

    return _canonicalize_roots(roots)


def _normalized_roots(roots: Iterable[str | os.PathLike[str]] | None) -> tuple[Path, ...]:
    return _canonicalize_roots(get_allowed_roots() if roots is None else roots)


def is_within_allowed_roots(
    path: str | os.PathLike[str], *, roots: Iterable[str | os.PathLike[str]] | None = None
) -> bool:
    """Return whether *path* resolves inside one of the allowed roots."""
    resolved = _resolve(path)
    return any(resolved.is_relative_to(root) for root in _normalized_roots(roots))


def ensure_within_allowed_roots(
    path: str | os.PathLike[str], *, roots: Iterable[str | os.PathLike[str]] | None = None
) -> Path:
    """Return the canonical *path*, or raise if it escapes the allowed roots.

    Passing *roots* confines the check to an explicit set (for example a storage
    provider validating against its own base directory). Otherwise the roots
    come from :func:`get_allowed_roots`.
    """
    resolved = _resolve(path)
    candidates = _normalized_roots(roots)
    if any(resolved.is_relative_to(root) for root in candidates):
        return resolved

    allowed = os.pathsep.join(str(root) for root in candidates) or "<none>"
    raise PathAccessDeniedError(
        f"Path '{path}' is outside the allowed Kontext storage roots ({allowed}). "
        f"Set {ALLOWED_PATHS_ENV} to permit additional directories."
    )
