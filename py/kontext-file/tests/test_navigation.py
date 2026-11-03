from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from kontext.data.models import ProjectFile
from kontext.file.helpers import file_to_model
from kontext.file.navigation import FileNavigationService
from kontext.schema import FileFormatType


class _FakeFileDataService:
    def __init__(self, files: list[ProjectFile]) -> None:
        self._files = files

    async def get_non_deleted_files_batch_by_cursor_async(
        self,
        project_id: UUID,
        cursor: UUID | None = None,
        batch_size: int = 200,
    ):
        return list(self._files)


def _file(
    name: str,
    prefix: str,
    project_id,
    *,
    owner_id=None,
    date_created: datetime | None = None,
    date_modified: datetime | None = None,
) -> ProjectFile:
    return ProjectFile(
        id=uuid4(),
        name=name,
        prefix=prefix,
        file_type=FileFormatType.CSV.value,
        size=1,
        project_id=project_id,
        owner_id=owner_id,
        date_created=date_created or datetime.now(UTC),
        date_modified=date_modified,
        is_deleted=False,
    )


@pytest.mark.asyncio
async def test_prefix_navigation_lists_child_folders_and_files() -> None:
    project_id = uuid4()
    files = [
        _file("root.csv", "", project_id),
        _file("nested.csv", "reports", project_id),
        _file("other.csv", "other", project_id),
    ]
    service = FileNavigationService(project_id, _FakeFileDataService(files))

    result = await service.list_prefix_navigation(
        project_id=project_id,
        prefix="",
        page_index=1,
        page_size=20,
        owner_id=None,
        file_types=None,
        filter_string=None,
        include_system_prefixes=False,
    )

    by_name = {item.name: item for item in result.items}
    assert by_name["root.csv"].path == "root.csv"
    assert by_name["reports"].content_type == "inode/directory"
    assert by_name["other"].content_type == "inode/directory"
    assert result.total_count == 3


@pytest.mark.asyncio
async def test_prefix_navigation_respects_owner_filter() -> None:
    project_id = uuid4()
    owner_id = uuid4()
    other_owner = uuid4()
    files = [
        _file("mine.csv", "", project_id, owner_id=owner_id),
        _file("theirs.csv", "", project_id, owner_id=other_owner),
    ]
    service = FileNavigationService(project_id, _FakeFileDataService(files))

    result = await service.list_prefix_navigation(
        project_id=project_id,
        prefix="",
        page_index=1,
        page_size=20,
        owner_id=owner_id,
        file_types=None,
        filter_string=None,
        include_system_prefixes=False,
    )

    names = [item.name for item in result.items]
    assert names == ["mine.csv"]


@pytest.mark.asyncio
async def test_prefix_navigation_orders_files_by_recency_desc() -> None:
    project_id = uuid4()
    files = [
        _file(
            "oldest.csv",
            "",
            project_id,
            date_created=datetime(2024, 1, 1, tzinfo=UTC),
        ),
        _file(
            "newest.csv",
            "",
            project_id,
            date_created=datetime(2024, 3, 1, tzinfo=UTC),
        ),
        _file(
            "modified_recently.csv",
            "",
            project_id,
            date_created=datetime(2024, 2, 1, tzinfo=UTC),
            date_modified=datetime(2024, 4, 1, tzinfo=UTC),
        ),
    ]
    service = FileNavigationService(project_id, _FakeFileDataService(files))

    result = await service.list_prefix_navigation(
        project_id=project_id,
        prefix="",
        page_index=1,
        page_size=20,
        owner_id=None,
        file_types=None,
        filter_string=None,
        include_system_prefixes=False,
    )

    assert [item.name for item in result.items] == [
        "modified_recently.csv",
        "newest.csv",
        "oldest.csv",
    ]


@pytest.mark.asyncio
async def test_prefix_navigation_keeps_folders_before_files() -> None:
    project_id = uuid4()
    files = [
        _file(
            "new_file.csv",
            "",
            project_id,
            date_created=datetime(2024, 6, 1, tzinfo=UTC),
        ),
        _file(
            "old_file.csv",
            "",
            project_id,
            date_created=datetime(2024, 1, 1, tzinfo=UTC),
        ),
        _file(
            "nested.csv",
            "z_folder",
            project_id,
            date_created=datetime(2024, 5, 1, tzinfo=UTC),
        ),
        _file(
            "other.csv",
            "a_folder",
            project_id,
            date_created=datetime(2024, 2, 1, tzinfo=UTC),
        ),
    ]
    service = FileNavigationService(project_id, _FakeFileDataService(files))

    result = await service.list_prefix_navigation(
        project_id=project_id,
        prefix="",
        page_index=1,
        page_size=20,
        owner_id=None,
        file_types=None,
        filter_string=None,
        include_system_prefixes=False,
    )

    names = [item.name for item in result.items]
    assert names[:2] == ["a_folder", "z_folder"]
    assert names[2:] == ["new_file.csv", "old_file.csv"]


def test_is_system_prefix_classification() -> None:
    assert FileNavigationService.is_system_prefix(".lakehouse")
    assert FileNavigationService.is_system_prefix(".knowledge")
    assert not FileNavigationService.is_system_prefix("reports")


def test_file_to_model_preserves_identity() -> None:
    project_id = uuid4()
    project_file = _file("root.csv", "", project_id)
    model = file_to_model(project_file)
    assert model.name == "root.csv"
    assert model.id == str(project_file.id)
