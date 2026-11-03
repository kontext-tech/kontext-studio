from kontext.runtime.local.config import get_default_local_file_types
from kontext.schema import FileFormatType


def test_default_local_file_types_include_jsonl():
    assert any(
        file_type.file_extension == ".jsonl" and file_type.file_format_type == FileFormatType.JSONL
        for file_type in get_default_local_file_types()
    )
