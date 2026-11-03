from uuid import UUID, uuid4

from kontext.file.processing import FileProcessingPlan, FileProcessingService
from kontext.schema import FileFormatType


def test_processing_target_classifies_lakehouse_data_files() -> None:
    service = FileProcessingService(project_id=str(uuid4()))

    assert (
        service.get_file_processing_target(
            filename="orders.csv",
            content_type="text/csv",
            file_type=FileFormatType.CSV,
        )
        == "lakehouse"
    )


def test_processing_target_skips_system_prefixes() -> None:
    service = FileProcessingService(project_id=str(uuid4()))

    assert (
        service.get_file_processing_target(
            filename="orders.csv",
            prefix=".lakehouse",
            content_type="text/csv",
            file_type=FileFormatType.CSV,
        )
        == "none"
    )


def test_build_processing_plan_ignores_old_target_for_new_files() -> None:
    service = FileProcessingService(project_id=str(uuid4()))
    file_id = uuid4()

    plan = service.build_file_processing_plan(
        file_id=file_id,
        new_filename="orders.csv",
        new_content_type="text/csv",
        new_file_type=FileFormatType.CSV,
    )

    assert isinstance(plan, FileProcessingPlan)
    assert plan.old_target == "none"
    assert plan.new_target == "lakehouse"
    assert plan.file_id == file_id


def test_build_processing_plan_detects_target_change() -> None:
    service = FileProcessingService(project_id=str(uuid4()))

    plan = service.build_file_processing_plan(
        file_id=UUID(int=1),
        old_filename="notes",
        old_content_type="application/octet-stream",
        old_file_type=FileFormatType.DEFAULT,
        new_filename="notes.md",
        new_content_type="text/markdown",
        new_file_type=FileFormatType.MARKDOWN,
    )

    # Default is not processed; Markdown is document-indexable.
    assert plan.old_target == "none"
    assert plan.new_target == "document"
