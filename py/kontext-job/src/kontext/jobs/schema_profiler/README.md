# Schema Profiler Module

## Overview

The Schema Profiler Module analyzes data files with DuckDB and extracts their
schema structure, column metadata, and statistics. It is used by the file
profiling service in `kontext-file` to produce `FileSchemaModel` /
`FileStatsModel` values.

Files are read through DuckDB using a resolved storage path. Only local
filesystem access is wired up today; the base class reads local paths directly.

## Supported File Formats

- **CSV / TSV / TXT** — delimited text with automatic delimiter detection
- **Parquet** — columnar format with native DuckDB support
- **JSON / JSONL** — standard JSON and JSON Lines
- **Excel** — `.xlsx` workbooks via `openpyxl` when installed

## Features

- **Automatic Schema Detection** — infers column names and types with DuckDB
- **Multi-Format Support** — dispatches to the right profiler by `FileFormatType`
- **Delimiter Detection** — detects separators for delimited text files
- **Type Inference** — maps DuckDB types to `ColumnDataType` via
  `type_mapping.map_duckdb_type_to_column_data_type`
- **Advanced Statistics** — null counts, distinct values, min/max ranges,
  completeness metrics, and top/sample values for categorical columns
- **Pydantic Models** — results and parameters are validated models
- **Context Manager Support** — DuckDB connections are closed on exit

## Architecture

1. **Profiler base** (`profiler_base.py`)
   - `SchemaProfilerBase` — abstract base; owns the DuckDB connection and
     `ProfilerParameters`. `storage_path` returns the raw `uri`.

2. **Per-format profilers**
   - `CsvSchemaProfiler` (`csv_profiler.py`) — CSV, TSV, and delimited text
   - `ParquetSchemaProfiler` (`parquet_profiler.py`) — Parquet
   - `JsonSchemaProfiler` (`json_profiler.py`) — JSON and JSONL
   - `ExcelSchemaProfiler` (`excel_profiler.py`) — Excel workbooks
   - `create_profiler()` (`profilers.py`) — factory keyed off
     `ProfilerParameters.file_type`

3. **Models** (`models.py`)
   - `ProfilerParameters` — inputs (`uri`, `file_type`, `project_id` scoping)
   - `SchemaProfilingResult` — `success`, `file_schema`, `file_stats`,
     `error_message`, `warnings`
   - `SchemaProfilingError` — raised on detection failures

4. **Type mapping** (`type_mapping.py`) — DuckDB type to `ColumnDataType`
   conversion plus `is_numeric_type` / `is_text_type` helpers.

## Usage

```python
from kontext.jobs.schema_profiler import (
    ProfilerParameters,
    create_profiler,
)
from kontext.schema import FileFormatType

params = ProfilerParameters(
    uri="/data/sales.csv",
    file_type=FileFormatType.CSV,
    file_name="sales.csv",
    file_size_bytes=2048,
    project_id="00000000-0000-0000-0000-000000000000",
)

with create_profiler(params) as profiler:
    result = profiler.profile()
    if result.success and result.file_schema:
        schema = result.file_schema
        for col in schema.columns:
            print(f"{col.name}: {col.data_type}")
    else:
        print(f"Error: {result.error_message}")
```

## Notes

- `ProfilerParameters.project_id` is a required UUID used for scoping.
- Only local filesystem paths are supported today. Object-storage backends can
  be added behind the same base class without changing call sites.
