from __future__ import annotations

import pytest

from kontext.common.utils.path_policy import PathAccessDeniedError
from kontext.storage.config import StorageConfig, StorageProvider
from kontext.storage.providers.local import LocalFilesystemProvider


def test_local_provider_uses_projects_prefix_for_relative_paths(tmp_path) -> None:
    provider = LocalFilesystemProvider(
        StorageConfig(
            provider=StorageProvider.LOCAL,
            local_base_path=str(tmp_path / "storage"),
        )
    )
    expected_uri = "file://" + str(
        tmp_path / "storage" / "projects" / "project-123" / "resources" / "orders.csv"
    )

    assert (
        provider.get_relative_path("project-123", "orders.csv")
        == "projects/project-123/resources/orders.csv"
    )
    assert provider.get_storage_uri("project-123", "orders.csv") == expected_uri


def _provider(tmp_path) -> LocalFilesystemProvider:
    return LocalFilesystemProvider(
        StorageConfig(
            provider=StorageProvider.LOCAL,
            local_base_path=str(tmp_path / "storage"),
        )
    )


def test_local_provider_rejects_parent_traversal(tmp_path) -> None:
    provider = _provider(tmp_path)

    with pytest.raises(PathAccessDeniedError):
        provider.resolve_path("../outside.txt")


async def test_local_provider_rejects_file_uri_outside_base(tmp_path) -> None:
    provider = _provider(tmp_path)

    with pytest.raises(PathAccessDeniedError):
        await provider.download_file(f"file://{tmp_path / 'secret.txt'}")


async def test_local_provider_allows_file_uri_inside_base(tmp_path) -> None:
    provider = _provider(tmp_path)
    target = tmp_path / "storage" / "projects" / "p1" / "resources" / "a.txt"
    target.parent.mkdir(parents=True)
    target.write_text("hello", encoding="utf-8")

    stream = await provider.download_file(f"file://{target}")

    assert stream.read() == b"hello"


async def test_local_provider_list_files_rejects_traversal(tmp_path) -> None:
    provider = _provider(tmp_path)

    with pytest.raises(PathAccessDeniedError):
        await provider.list_files(project_id="../../..")
