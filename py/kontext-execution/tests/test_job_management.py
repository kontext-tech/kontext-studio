from kontext.execution.job_management import get_job_type_service
from kontext.schema import JobCategory, JobExecutionRuntime


def test_get_job_type_service_returns_synthetic_workflow_root_metadata():
    metadata = get_job_type_service("python.workflow.chat_upload_preparation.Root")

    assert metadata.type == "python.workflow.chat_upload_preparation.Root"
    assert metadata.name == "Chat Upload Preparation Workflow Root"
    assert metadata.category == JobCategory.PROCESSING
    assert metadata.runtime == JobExecutionRuntime.PYTHON
    assert metadata.is_system_job is True
    assert metadata.parameters == []
