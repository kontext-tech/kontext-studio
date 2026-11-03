from __future__ import annotations

import pathlib
import threading

from kontext.storage.config import StorageConfig, StorageProvider
from kontext.storage.providers.local import LocalFilesystemProvider


def _provider(tmp_path: pathlib.Path) -> LocalFilesystemProvider:
    return LocalFilesystemProvider(
        StorageConfig(
            provider=StorageProvider.LOCAL,
            local_base_path=str(tmp_path / "storage"),
        )
    )


async def test_upload_file_writes_full_content(tmp_path) -> None:
    provider = _provider(tmp_path)
    result = await provider.upload_file(
        project_id="project-1",
        filename="notebook.kontext",
        content=b'{"blocks": [1, 2, 3]}',
    )

    assert result.size == 21
    assert pathlib.Path(result.uri.removeprefix("file://")).read_bytes() == (
        b'{"blocks": [1, 2, 3]}'
    )


async def test_upload_file_is_atomic_and_leaves_no_temp_files(tmp_path) -> None:
    """Replaces must be atomic so readers never observe a torn file.

    Regression: writes used truncate-then-write on the destination, so a
    concurrent download (or the notebook tools reloading the file) could read
    fewer bytes than the declared Content-Length
    (ERR_CONTENT_LENGTH_MISMATCH) or miss freshly written blocks
    ("Block not found").
    """
    provider = _provider(tmp_path)

    for size in (10, 500, 30_000):
        await provider.upload_file(
            project_id="project-1",
            filename="notebook.kontext",
            content=b"x" * size,
        )
        target = tmp_path / "storage" / "projects" / "project-1" / "resources" / "notebook.kontext"
        assert target.stat().st_size == size

    directory = target.parent
    leftovers = [entry.name for entry in directory.iterdir() if entry.name != "notebook.kontext"]
    assert leftovers == []


async def test_upload_file_never_publishes_partial_content(tmp_path) -> None:
    """A concurrent reader must only ever see complete previous/next content."""
    provider = _provider(tmp_path)
    small = b'{"blocks": []}'
    large = b'{"blocks": ["' + b"a" * 10_000 + b'"]}'

    await provider.upload_file(project_id="project-1", filename="notebook.kontext", content=small)
    target = tmp_path / "storage" / "projects" / "project-1" / "resources" / "notebook.kontext"

    stop = threading.Event()
    seen_partial: list[bytes] = []

    def churn():
        import asyncio

        async def loop():
            while not stop.is_set():
                await provider.upload_file(
                    project_id="project-1",
                    filename="notebook.kontext",
                    content=large,
                )
                await provider.upload_file(
                    project_id="project-1",
                    filename="notebook.kontext",
                    content=small,
                )

        asyncio.run(loop())

    thread = threading.Thread(target=churn)
    thread.start()

    try:
        for _ in range(200):
            content = target.read_bytes()
            if content not in (small, large):
                seen_partial.append(content)
                break
    finally:
        stop.set()
        thread.join()

    assert seen_partial == []
