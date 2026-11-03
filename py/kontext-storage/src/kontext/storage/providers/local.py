"""
Local filesystem storage provider.
"""

from __future__ import annotations

import asyncio
import os
import pathlib
import tempfile
import time
from contextlib import suppress
from io import BytesIO
from typing import BinaryIO

from kontext.common.utils.path_policy import ensure_within_allowed_roots

from ..config import StorageConfig
from .base import BaseStorageProvider, StorageResult

_DEFAULT_BASE = pathlib.Path.home() / ".kontext" / "storage"

# Bounded retry for the replace step on Windows, where a concurrent reader
# holding the destination open makes os.replace fail with PermissionError
# until the last handle closes. The backoff tops out at ~6 seconds total.
_REPLACE_RETRIES = 8
_REPLACE_RETRY_BASE_SECONDS = 0.02


def _write_and_replace(
    descriptor: int, data: bytes, temp_path: pathlib.Path, destination: pathlib.Path
) -> None:
    """Write *data* to the temp file descriptor and atomically replace *destination*."""
    with os.fdopen(descriptor, "wb") as temp_file:
        temp_file.write(data)
    _replace_with_windows_retry(temp_path, destination)


def _replace_with_windows_retry(source: pathlib.Path, destination: pathlib.Path) -> None:
    """Atomically move the fully written temp file over the destination.

    POSIX renames are atomic even with concurrent readers; only Windows needs
    a brief retry loop while a reader keeps the destination locked.
    """
    for attempt in range(_REPLACE_RETRIES):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if os.name != "nt" or attempt == _REPLACE_RETRIES - 1:
                raise
            time.sleep(_REPLACE_RETRY_BASE_SECONDS * (2**attempt))


class LocalFilesystemProvider(BaseStorageProvider):
    """Storage provider backed by the local filesystem."""

    def __init__(self, config: StorageConfig) -> None:
        super().__init__(config)
        raw_base = (
            config.local_base_path
            or os.getenv("KONTEXT_LOCAL_STORAGE_PATH", "")
            or str(_DEFAULT_BASE)
        )
        self._base = pathlib.Path(raw_base).resolve()
        self._base.mkdir(parents=True, exist_ok=True)
        self.logger.info("LocalFilesystemProvider base: %s", self._base)

    def _full_path(self, relative: str) -> pathlib.Path:
        if relative.startswith("file://"):
            candidate = pathlib.Path(relative[7:])
        else:
            candidate = self._base / relative
        # Stored URIs and filenames can contain ``..`` or absolute segments.
        # Canonicalize and reject anything that escapes the provider's own
        # configured root so a crafted path can never read or write outside it.
        return ensure_within_allowed_roots(candidate, roots=(self._base,))

    def _uri(self, relative: str) -> str:
        return f"file://{self._base / relative}"

    async def upload_file(
        self,
        project_id: str,
        filename: str,
        content: BinaryIO | bytes,
        prefix: str | None = None,
        content_type: str | None = None,
    ) -> StorageResult:
        relative = self.get_relative_path(
            project_id=project_id,
            filename=filename,
            prefix=prefix,
        )
        dest = self._full_path(relative)
        dest.parent.mkdir(parents=True, exist_ok=True)

        data = content if isinstance(content, bytes) else content.read()  # type: ignore[union-attr]

        # Write through a temporary file and atomically replace the target so
        # concurrent readers (e.g. a download endpoint streaming while agent
        # tool calls persist into the same file) always observe either the
        # previous or the fully written content - never a partial body. The
        # whole write-and-replace sequence is synchronous disk I/O, so it runs
        # in a worker thread and never holds up the event loop (on Windows the
        # replace step may also wait out a reader-wrangling retry).
        descriptor, temp_name = tempfile.mkstemp(
            dir=dest.parent, prefix=f".{dest.name}.", suffix=".tmp"
        )
        temp_path = pathlib.Path(temp_name)
        try:
            await asyncio.to_thread(_write_and_replace, descriptor, data, temp_path, dest)
        except BaseException:
            with suppress(OSError):
                temp_path.unlink()
            raise

        return StorageResult(path=relative, uri=self._uri(relative), size=len(data))

    async def download_file(self, path: str) -> BytesIO:
        full = self._full_path(path)
        return BytesIO(full.read_bytes())

    async def download_range(self, path: str, offset: int, length: int) -> BytesIO:
        full = self._full_path(path)
        with full.open("rb") as fh:
            fh.seek(offset)
            return BytesIO(fh.read(length))

    async def delete_file(self, path: str) -> bool:
        full = self._full_path(path)
        if not full.exists():
            return False
        full.unlink()
        return True

    async def file_exists(self, path: str) -> bool:
        return self._full_path(path).exists()

    def resolve_path(self, path: str) -> pathlib.Path:  # type: ignore[override]
        return self._full_path(path)

    async def get_file_size(self, path: str) -> int | None:
        full = self._full_path(path)
        if not full.exists():
            return None
        return full.stat().st_size

    async def list_files(self, *, project_id: str, prefix: str | None = None) -> list[str]:
        """List stored relative paths under a project's resources/<prefix> dir."""
        from kontext.common.utils.file_storage import normalize_project_file_prefix

        normalized_prefix = normalize_project_file_prefix(prefix)
        directory = ensure_within_allowed_roots(
            self._base / "projects" / project_id / "resources", roots=(self._base,)
        )
        if normalized_prefix:
            directory = directory / normalized_prefix
        if not directory.is_dir():
            return []
        return [
            str(path.relative_to(self._base))
            for path in sorted(directory.rglob("*"))
            if path.is_file()
        ]

    def get_storage_uri(self, project_id: str, filename: str, prefix: str | None = None) -> str:
        relative = self.get_relative_path(
            project_id=project_id,
            filename=filename,
            prefix=prefix,
        )
        return self._uri(relative)

    def get_relative_path(self, project_id: str, filename: str, prefix: str | None = None) -> str:
        return super().get_relative_path(project_id, filename, prefix)
