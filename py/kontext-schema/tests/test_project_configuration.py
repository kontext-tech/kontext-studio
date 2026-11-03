from __future__ import annotations

import pytest
from pydantic import ValidationError

from kontext.schema import ProjectConfiguration


def test_from_dict_accepts_current_project_configuration_shape():
    config = ProjectConfiguration.from_dict(
        {
            "allowed_file_types": [
                {
                    "file_extension": ".csv",
                    "file_format_type": "CSV",
                    "allowed_content_types": ["text/csv"],
                }
            ],
            "max_file_bytes_size": 1024,
            "total_storage_allocation_bytes": 4096,
            "features": ["Chat"],
            "default_query_engine": "DuckDB",
        }
    )

    assert config is not None
    assert config.default_query_engine is not None
    assert config.default_query_engine.value == "DuckDB"


@pytest.mark.parametrize(
    "legacy_payload",
    [
        {
            "allowed_file_types": [],
            "max_file_bytes_size": 1024,
            "total_storage_allocation_bytes": 4096,
            "features": ["Chat"],
            "allowed_llm_model_ids": ["legacy-model"],
        },
        {
            "allowed_file_types": [],
            "max_file_bytes_size": 1024,
            "total_storage_allocation_bytes": 4096,
            "features": ["Chat"],
            "is_local": True,
        },
        {
            "allowedFileTypes": [],
            "maxFileBytesSize": 1024,
            "totalStorageAllocationBytes": 4096,
            "features": ["Chat"],
            "isLocal": True,
        },
    ],
)
def test_from_dict_rejects_legacy_project_configuration_fields(legacy_payload):
    with pytest.raises(ValidationError):
        ProjectConfiguration.from_dict(legacy_payload)
