"""Generic utilities shared across Kontext packages.

The facade is lazy so importing one helper does not load every utility module.
Prefer importing from the owning submodule when the intent is clearer.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

_EXPORTS: dict[str, str] = {
    "poll_until": "async_utils",
    "format_datetime_utc": "datetime_utils",
    "utc_now": "datetime_utils",
    "utc_now_iso": "datetime_utils",
    "is_local_dev_environment": "environment",
    "get_file_storage_path": "file_storage",
    "model_validate_stored": "json_compat",
    "ALLOWED_PATHS_ENV": "path_policy",
    "PathAccessDeniedError": "path_policy",
    "ensure_within_allowed_roots": "path_policy",
    "get_allowed_roots": "path_policy",
    "is_within_allowed_roots": "path_policy",
}

if TYPE_CHECKING:
    from .async_utils import poll_until
    from .datetime_utils import format_datetime_utc, utc_now, utc_now_iso
    from .environment import is_local_dev_environment
    from .file_storage import get_file_storage_path
    from .json_compat import model_validate_stored
    from .path_policy import (
        ALLOWED_PATHS_ENV,
        PathAccessDeniedError,
        ensure_within_allowed_roots,
        get_allowed_roots,
        is_within_allowed_roots,
    )


def __getattr__(name: str):
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module = import_module(f"{__name__}.{module_name}")
    return getattr(module, name)


__all__ = sorted(_EXPORTS)  # pyright: ignore[reportUnsupportedDunderAll]
