from kontext.file.lakehouse_ingest_models import (
    LakehouseIngestFailure,
    LakehouseIngestResultData,
)


def test_lakehouse_ingest_result_data_preserves_job_payload_shape():
    result_data = LakehouseIngestResultData(
        connection_id="11111111-1111-4111-8111-111111111111",
        successful_file_ids=["22222222-2222-4222-8222-222222222222"],
        failed_files=[
            LakehouseIngestFailure(
                file_id="33333333-3333-4333-8333-333333333333",
                error="Profiling returned no schema",
            )
        ],
        entity_count=2,
        invalidated_session_ids=["44444444-4444-4444-8444-444444444444"],
    )

    assert result_data.to_job_result_payload() == {
        "connection_id": "11111111-1111-4111-8111-111111111111",
        "successful_file_ids": ["22222222-2222-4222-8222-222222222222"],
        "failed_files": [
            {
                "id": "33333333-3333-4333-8333-333333333333",
                "error": "Profiling returned no schema",
            }
        ],
        "entity_count": 2,
        "invalidated_session_ids": ["44444444-4444-4444-8444-444444444444"],
    }
