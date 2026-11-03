"""
Data lake constants for Kontext.

This file contains constants that are synchronized with the main platform constants.
Keep these in sync with:
- C#: backend/Kontext.Job/Constants/DataLakeConstants.cs
- TypeScript: ts/common/src/constants/dataLakeConstants.ts
"""

from kontext.schema import FileFormatType


class DataLakeConstants:
    """Constants related to data lake operations and profiling."""

    # File format types that support data profiling and should be
    # included in raw lakehouse namespaces.
    # NOTE: Keep this synchronized with DataLakeConstants.cs and dataLakeConstants.ts
    SUPPORTED_DATA_FILE_TYPES = [
        FileFormatType.CSV,
        FileFormatType.TSV,
        FileFormatType.PARQUET,
        FileFormatType.JSON,
        FileFormatType.JSONL,
        FileFormatType.EXCEL,
    ]

    @staticmethod
    def is_supported_data_file_type(file_type: FileFormatType) -> bool:
        """Check if a file format type is supported for data profiling."""
        return file_type in DataLakeConstants.SUPPORTED_DATA_FILE_TYPES

    @staticmethod
    def get_supported_data_file_types() -> list[FileFormatType]:
        """Get a list of all supported data file format types."""
        return DataLakeConstants.SUPPORTED_DATA_FILE_TYPES.copy()
