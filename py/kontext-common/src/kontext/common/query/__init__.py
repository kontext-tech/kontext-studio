"""Shared query contracts.

Holds the engine port (``engine``) and the low-level, dependency-light session
primitives (storage paths, compatibility predicates, execution locks, scope
hydration). These are used by both the query orchestration layer
(``kontext-query``) and the in-process compute adapters (``kontext-engine``);
keeping them in ``kontext-common`` lets the engine depend only on contracts
rather than reaching up into ``kontext-query``.

The facade is lazy so importing one primitive does not load the whole query
contract surface.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

_EXPORTS: dict[str, str] = {
    "QueryEngineType": "engine",
    "QueryExecutionEngine": "engine",
    "should_persist_result": "result_materialization",
    "get_session_timestamp": "session_compatibility",
    "is_session_compatible": "session_compatibility",
    "normalize_engine_value": "session_compatibility",
    "requires_catalog_connection": "session_compatibility",
    "sort_sessions_by_preference": "session_compatibility",
    "get_session_lock": "session_locks",
    "session_execution_lock": "session_locks",
    "hydrate_session_scope": "session_scope",
    "delete_session_database_file": "session_storage",
    "ensure_session_directory_exists": "session_storage",
    "get_project_sessions_directory": "session_storage",
    "get_session_database_path": "session_storage",
}

if TYPE_CHECKING:
    from .engine import QueryEngineType, QueryExecutionEngine
    from .result_materialization import should_persist_result
    from .session_compatibility import (
        get_session_timestamp,
        is_session_compatible,
        normalize_engine_value,
        requires_catalog_connection,
        sort_sessions_by_preference,
    )
    from .session_locks import get_session_lock, session_execution_lock
    from .session_scope import hydrate_session_scope
    from .session_storage import (
        delete_session_database_file,
        ensure_session_directory_exists,
        get_project_sessions_directory,
        get_session_database_path,
    )


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f"{__name__}.{module_name}")
    return getattr(module, name)


__all__ = sorted(_EXPORTS)  # pyright: ignore[reportUnsupportedDunderAll]
