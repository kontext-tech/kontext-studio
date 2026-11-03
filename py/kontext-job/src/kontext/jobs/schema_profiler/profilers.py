"""Schema profilers for different file types using DuckDB with local storage."""

from kontext.schema import FileFormatType

from .csv_profiler import CsvSchemaProfiler
from .excel_profiler import ExcelSchemaProfiler
from .json_profiler import JsonSchemaProfiler
from .models import ProfilerParameters
from .parquet_profiler import ParquetSchemaProfiler
from .profiler_base import SchemaProfilerBase


def create_profiler(params: ProfilerParameters) -> SchemaProfilerBase:
    """Factory function to create the appropriate profiler based on file type"""
    if params.file_type in [FileFormatType.CSV, FileFormatType.TSV]:
        return CsvSchemaProfiler(params)
    elif params.file_type == FileFormatType.PARQUET:
        return ParquetSchemaProfiler(params)
    elif params.file_type in [FileFormatType.JSON, FileFormatType.JSONL]:
        return JsonSchemaProfiler(params)
    elif params.file_type == FileFormatType.EXCEL:
        return ExcelSchemaProfiler(params)
    else:
        raise ValueError(f"Unsupported file type: {params.file_type}")
