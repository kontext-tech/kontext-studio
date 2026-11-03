"""Excel schema profiler using DuckDB's excel extension."""

import logging
from typing import Any
from urllib.parse import unquote, urlparse

import duckdb

from kontext.schema import (
    ColumnModel,
    ColumnStatsModel,
    FileFormatType,
    FileMetadataModel,
    FileSchemaModel,
    FileStatsModel,
    TableSchemaModel,
    TableStatsModel,
)

try:
    from openpyxl import load_workbook

    HAS_OPENPYXL = True
except ImportError:
    HAS_OPENPYXL = False
    load_workbook = None  # type: ignore

import contextlib

from kontext.common.utils.datetime_utils import utc_now
from kontext.common.utils.sql_utils import (
    escape_sql_literal,
    generate_temp_view_name,
    parse_describe_nullability,
    quote_identifier,
)

from .models import ProfilerParameters, SchemaProfilingError, SchemaProfilingResult
from .profiler_base import SchemaProfilerBase
from .type_mapping import (
    is_numeric_type,
    is_text_type,
    map_duckdb_type_to_column_data_type,
)


class ExcelSchemaProfiler(SchemaProfilerBase):
    """Schema profiler for Excel (.xlsx, .xls) files using DuckDB's excel extension.

    DuckDB's excel extension provides read_xlsx() function for reading Excel
    files. For files with multiple worksheets, this profiler will analyze the
    first sheet by default.
    """

    STATS_SOURCE_PRIMARY = "duckdb_desc"
    PROFILING_METHOD = "duckdb_excel"
    DEFAULT_ENCODING = "utf-8"

    def __init__(self, params: ProfilerParameters):
        super().__init__(params)
        self.logger = logging.getLogger(__name__)
        self._temp_view_name = generate_temp_view_name("temp_excel_view")

    @property
    def _conn(self) -> "duckdb.DuckDBPyConnection":
        """Get DuckDB connection or raise error if not initialized."""
        if self._connection is None:
            raise SchemaProfilingError("DuckDB connection not initialized")
        return self._connection

    def _query_scalar(self, sql: str) -> Any:
        """Execute SQL and return the first column of the first row."""
        result = self._conn.execute(sql).fetchone()
        if result is None:
            return None
        if isinstance(result, tuple | list):
            return result[0] if result else None
        return result

    def profile(self) -> SchemaProfilingResult:
        """Profile Excel file using DuckDB's excel extension.

        Profiles all sheets in the Excel file and creates a multi-table
        schema structure using subSchemas (single-item array for single-sheet files).
        """
        try:
            self.logger.info(f"Starting Excel schema profiling for {self.storage_path}")

            # Ensure connection is initialized
            _ = self._conn

            # Install excel extension if not already installed
            self._ensure_excel_extension()

            # Discover all sheet names
            discovered_sheets = self._discover_sheet_names()

            sheet_names = [sheet_name for sheet_name in discovered_sheets if sheet_name]

            if not sheet_names:
                self.logger.info(
                    "Could not discover Excel sheet names for %s; "
                    "falling back to DuckDB's default worksheet selection",
                    self.storage_path,
                )
                return self._profile_single_sheet()

            self.logger.info(f"Discovered {len(sheet_names)} sheet(s) in Excel file: {sheet_names}")

            if len(sheet_names) == 1:
                # Profile single sheet (existing behavior)
                return self._profile_single_sheet(sheet_names[0])

            # Profile multiple sheets
            return self._profile_multi_sheet(sheet_names)

        except Exception as e:
            error_msg = f"Failed to profile Excel file {self.storage_path}: {e!s}"
            self.logger.error(error_msg, exc_info=True)
            return SchemaProfilingResult.failure_result(error_msg, [error_msg])

        finally:
            self._cleanup_temp_resources()

    def _ensure_excel_extension(self) -> None:
        """Ensure the excel extension is installed and loaded.

        Note: This is also done in configure_duckdb_engine(), but we ensure it here
        explicitly in case the profiler is used with a custom connection.
        """
        try:
            self._conn.execute("INSTALL excel;")
            self._conn.execute("LOAD excel;")
            self.logger.debug("Excel extension loaded")
        except Exception as e:
            # Extension might already be loaded, which is fine if the error
            # message says so
            error_msg = str(e).lower()
            if "already loaded" in error_msg or "already installed" in error_msg:
                self.logger.debug(f"Excel extension already loaded/installed: {e!s}")
            else:
                self.logger.warning(f"Excel extension setup failed: {e!s}")
                # We don't raise here as it might still work if it was pre-installed

    def _create_excel_view(self, sheet_name: str | None = None) -> None:
        """Create a temporary view from the Excel file using read_xlsx().

        Args:
            sheet_name: Optional sheet name to profile (used internally)
        """
        try:
            # Use read_xlsx to read Excel file
            # Note: 'sheet' parameter specifies which worksheet to read
            storage_path_lit = escape_sql_literal(self.storage_path)

            params = [storage_path_lit]
            if sheet_name:
                sheet_name_lit = escape_sql_literal(sheet_name)
                params.append(f"sheet={sheet_name_lit}")

            params_str = ", ".join(params)
            sql = f"""
                CREATE OR REPLACE TEMP VIEW {self._temp_view_name} AS
                SELECT * FROM read_xlsx({params_str})
            """

            self._conn.execute(sql)
            self.logger.debug(f"Created Excel view: {self._temp_view_name}")
        except Exception as e:
            raise SchemaProfilingError(f"Failed to create Excel view: {e!s}") from e

    def _extract_schema_info(self) -> list[tuple]:
        """Extract column schema information using DESCRIBE."""
        try:
            result = self._conn.execute(f"DESCRIBE {self._temp_view_name}").fetchall()

            # DESCRIBE returns: (column_name, column_type, null, key, default, extra)
            schema_info = [(row[0], row[1], row[2]) for row in result]
            self.logger.debug(f"Extracted schema: {len(schema_info)} columns")
            return schema_info
        except Exception as e:
            raise SchemaProfilingError(f"Failed to extract schema info: {e!s}") from e

    def _get_row_count(self) -> int:
        """Get total row count from the Excel file."""
        try:
            row_count = self._query_scalar(f"SELECT COUNT(*) FROM {self._temp_view_name}")
            row_count = int(row_count) if row_count is not None else 0
            self.logger.debug(f"Row count: {row_count}")
            return row_count
        except Exception as e:
            self.logger.warning(f"Failed to get row count: {e!s}")
            return 0

    def _get_column_stats(self, col_name: str, col_type: str) -> ColumnStatsModel:
        """Get statistics for a column."""
        try:
            col_id = quote_identifier(col_name)

            # Get null count
            null_count_sql = f"""
                SELECT COUNT(*) FROM {self._temp_view_name}
                WHERE {col_id} IS NULL
            """
            null_count = self._query_scalar(null_count_sql) or 0

            # Get distinct count
            distinct_count_sql = f"""
                SELECT COUNT(DISTINCT {col_id}) FROM {self._temp_view_name}
                WHERE {col_id} IS NOT NULL
            """
            distinct_count = self._query_scalar(distinct_count_sql) or 0

            # Get total count for completeness calculation
            total_query = f"SELECT COUNT(*) FROM {self._temp_view_name}"
            total_count = self._query_scalar(total_query) or 0

            # Calculate completeness score
            completeness_score = (
                (total_count - null_count) / total_count if total_count > 0 else 0.0
            )

            # Initialize optional fields
            min_value = None
            max_value = None
            avg_value = None
            std_dev = None
            max_length = None
            top_values = None

            # Add type-specific statistics
            if is_numeric_type(col_type):
                try:
                    numeric_query = f"""
                        SELECT
                            MIN(CAST({col_id} AS DOUBLE)) as min_val,
                            MAX(CAST({col_id} AS DOUBLE)) as max_val,
                            AVG(CAST({col_id} AS DOUBLE)) as avg_val,
                            STDDEV(CAST({col_id} AS DOUBLE)) as std_dev
                        FROM {self._temp_view_name}
                        WHERE {col_id} IS NOT NULL
                    """
                    numeric_result = self._conn.execute(numeric_query).fetchone()
                    if numeric_result:
                        min_value = numeric_result[0]
                        max_value = numeric_result[1]
                        avg_value = numeric_result[2]
                        std_dev = numeric_result[3]
                except Exception as e:
                    self.logger.warning(f"Failed to get numeric stats for {col_name}: {e}")

            elif is_text_type(col_type):
                try:
                    text_query = f"""
                        SELECT MAX(LENGTH({col_id})) as max_length
                        FROM {self._temp_view_name}
                        WHERE {col_id} IS NOT NULL
                    """
                    max_length = self._query_scalar(text_query)
                except Exception as e:
                    self.logger.warning(f"Failed to get text stats for {col_name}: {e}")

            # Get top values for categorical data
            if distinct_count <= self.CATEGORICAL_THRESHOLD:  # Only for low-cardinality columns
                try:
                    top_values_query = f"""
                        SELECT {col_id}, COUNT(*) as freq
                        FROM {self._temp_view_name}
                        WHERE {col_id} IS NOT NULL
                        GROUP BY {col_id}
                        ORDER BY freq DESC
                        LIMIT {self.TOP_VALUES_LIMIT}
                    """
                    top_values_result = self._conn.execute(top_values_query).fetchall()
                    if top_values_result:
                        top_values = {str(row[0]): row[1] for row in top_values_result}
                except Exception as e:
                    self.logger.warning(f"Failed to get top values for {col_name}: {e}")

            return ColumnStatsModel(
                column_name=col_name,
                distinct_count=distinct_count,
                null_count=null_count,
                completeness_score=completeness_score,
                min_value=min_value,
                max_value=max_value,
                std_dev=std_dev,
                median_value=None,
                avg_value=avg_value,
                max_length=max_length,
                top_values=top_values,
                true_count=None,
                false_count=None,
                true_ratio=None,
                stats_source=self.STATS_SOURCE_PRIMARY,
            )
        except Exception as e:
            self.logger.warning(f"Failed to get stats for column {col_name}: {e!s}")
            return ColumnStatsModel(
                column_name=col_name,
                distinct_count=0,
                null_count=0,
                completeness_score=0.0,
            )

    def _discover_sheet_names(self) -> list[str]:
        """Discover all sheet names in the Excel file.

        Uses openpyxl to read sheet names from the Excel file.
        Supports local filesystem paths.
        """
        if not HAS_OPENPYXL:
            self.logger.warning("openpyxl not available - cannot discover sheets")
            return []

        # Type guard for Pylance
        assert load_workbook is not None, (
            "load_workbook should be available when HAS_OPENPYXL is True"
        )

        try:
            path = self._resolve_workbook_path()

            wb = load_workbook(path, read_only=True, data_only=True)
            sheet_names = wb.sheetnames
            wb.close()

            return sheet_names
        except Exception as e:
            self.logger.warning(f"Failed to discover sheet names with openpyxl: {e}")
            return []

    def _resolve_workbook_path(self) -> str:
        """Resolve local file URIs for openpyxl sheet discovery."""
        path = self.storage_path
        if not path.startswith("file://"):
            return path

        parsed = urlparse(path)
        local_path = parsed.path
        if parsed.netloc and parsed.netloc != "localhost":
            local_path = f"//{parsed.netloc}{parsed.path}"
        return unquote(local_path)

    def _profile_single_sheet(self, sheet_name: str | None = None) -> SchemaProfilingResult:
        """Profile a single sheet using array-based structure."""
        try:
            # Create temporary view for Excel file
            self._create_excel_view(sheet_name)

            # Extract schema using DuckDB's DESCRIBE
            schema_info = self._extract_schema_info()

            # Get row count
            row_count = self._get_row_count()

            # Build columns
            columns = []
            for col_name, col_type, col_nullable in schema_info:
                data_type = map_duckdb_type_to_column_data_type(col_type)
                column = ColumnModel(
                    name=col_name,
                    data_type=data_type,
                    nullable=parse_describe_nullability(col_nullable),
                    description=None,
                    max_length=None,
                    precision=None,
                    scale=None,
                    physical_type=None,
                    logical_type=None,
                    encoding=None,
                    column_order=len(columns),
                )
                columns.append(column)

            # Get column stats
            column_stats = []
            for col_name, col_type, _ in schema_info:
                stats = self._get_column_stats(col_name, col_type)
                column_stats.append(stats)

            # Calculate null percentage
            total_nulls = sum(s.null_count or 0 for s in column_stats)
            total_cells = row_count * len(column_stats) if row_count and column_stats else 0
            null_percentage = total_nulls / total_cells if total_cells > 0 else 0.0

            # Create metadata
            metadata = FileMetadataModel(
                file_name=self.file_name,
                file_type=FileFormatType.EXCEL,
                encoding=self.DEFAULT_ENCODING,
                compression_type=None,
                delimiter=None,
                has_header=True,
                format_specific_metadata={
                    "sheet_count": 1,
                    "sheet_names": [sheet_name] if sheet_name else ["default"],
                },
            )

            # Create array-based schema (single item)
            table_name = sheet_name if sheet_name else self.file_name

            file_schema = FileSchemaModel(
                metadata=metadata,
                sub_schemas=[
                    TableSchemaModel(
                        table_name=table_name,
                        columns=columns,
                        is_partitioned=False,
                        partition_columns=None,
                    )
                ],
                version="1.0",
                last_modified=None,
                serde_info=None,
            )

            # Create array-based stats (single item)
            file_stats = FileStatsModel(
                profiling_date=utc_now(),
                profiling_method=self.PROFILING_METHOD,
                sub_schemas=[
                    TableStatsModel(
                        table_name=table_name,
                        estimated_row_count=row_count,
                        null_percentage=null_percentage,
                        column_stats=column_stats,
                    )
                ],
                warnings=None,
                additional_metadata={
                    "stats_source": self.STATS_SOURCE_PRIMARY,
                    "sheet_count": 1,
                },
            )

            self.logger.info(
                f"Successfully profiled Excel sheet '{sheet_name}': "
                f"{len(schema_info)} columns, {row_count} rows"
            )
            return SchemaProfilingResult.success_result(file_schema, file_stats)
        except Exception as e:
            error_msg = f"Failed to profile sheet '{sheet_name}': {e!s}"
            self.logger.error(error_msg, exc_info=True)
            return SchemaProfilingResult.failure_result(error_msg, [error_msg])

    def _profile_multi_sheet(self, sheet_names: list[str]) -> SchemaProfilingResult:
        """Profile multiple sheets and create array-based structure."""
        try:
            sub_schemas = []
            sub_stats = []
            warnings = []

            for sheet_name in sheet_names:
                try:
                    self.logger.info(f"Profiling sheet: {sheet_name}")

                    # Create temporary view for this sheet
                    self._create_excel_view(sheet_name)

                    # Extract schema
                    schema_info = self._extract_schema_info()
                    row_count = self._get_row_count()

                    # Build columns for this sheet
                    columns = []
                    for col_name, col_type, col_nullable in schema_info:
                        data_type = map_duckdb_type_to_column_data_type(col_type)
                        column = ColumnModel(
                            name=col_name,
                            data_type=data_type,
                            nullable=parse_describe_nullability(col_nullable),
                            description=None,
                            max_length=None,
                            precision=None,
                            scale=None,
                            physical_type=None,
                            logical_type=None,
                            encoding=None,
                            column_order=len(columns),
                        )
                        columns.append(column)

                    # Append sub-schema to array
                    sub_schemas.append(
                        TableSchemaModel(
                            table_name=sheet_name,
                            columns=columns,
                            is_partitioned=False,
                            partition_columns=None,
                        )
                    )

                    # Get column stats
                    column_stats = []
                    for col_name, col_type, _ in schema_info:
                        stats = self._get_column_stats(col_name, col_type)
                        column_stats.append(stats)

                    # Calculate null percentage for this sheet
                    total_nulls = sum(s.null_count or 0 for s in column_stats)
                    total_cells = row_count * len(column_stats) if row_count and column_stats else 0
                    null_percentage = total_nulls / total_cells if total_cells > 0 else 0.0

                    # Append sub-stats to array
                    sub_stats.append(
                        TableStatsModel(
                            table_name=sheet_name,
                            estimated_row_count=row_count,
                            null_percentage=null_percentage,
                            column_stats=column_stats,
                        )
                    )

                    self.logger.info(
                        f"Successfully profiled sheet '{sheet_name}': "
                        f"{len(schema_info)} columns, {row_count} rows"
                    )

                except Exception as e:
                    error_msg = f"Failed to profile sheet '{sheet_name}': {e!s}"
                    self.logger.warning(error_msg)
                    warnings.append(error_msg)
                finally:
                    # Clean up temp view
                    with contextlib.suppress(Exception):
                        self._conn.execute(f"DROP VIEW IF EXISTS {self._temp_view_name}")

            if not sub_schemas:
                return SchemaProfilingResult.failure_result(
                    "Failed to profile any sheets", warnings
                )

            # Create metadata
            metadata = FileMetadataModel(
                file_name=self.file_name,
                file_type=FileFormatType.EXCEL,
                encoding=self.DEFAULT_ENCODING,
                compression_type=None,
                delimiter=None,
                has_header=True,
                format_specific_metadata={
                    "sheet_count": len(sheet_names),
                    "sheet_names": sheet_names,
                },
            )

            # Create array-based schema
            file_schema = FileSchemaModel(
                metadata=metadata,
                sub_schemas=sub_schemas,
                version="1.0",
                last_modified=None,
                serde_info=None,
            )

            # Create array-based stats
            file_stats = FileStatsModel(
                profiling_date=utc_now(),
                profiling_method=self.PROFILING_METHOD,
                sub_schemas=sub_stats,
                warnings=warnings if warnings else None,
                additional_metadata={
                    "stats_source": self.STATS_SOURCE_PRIMARY,
                    "sheet_count": len(sub_schemas),
                },
            )

            self.logger.info(f"Successfully profiled Excel file with {len(sub_schemas)} sheets")
            return SchemaProfilingResult.success_result(file_schema, file_stats)

        except Exception as e:
            error_msg = f"Failed to profile multi-sheet Excel file: {e!s}"
            self.logger.error(error_msg, exc_info=True)
            return SchemaProfilingResult.failure_result(error_msg, [error_msg])

    def _cleanup_temp_resources(self) -> None:
        """Clean up temporary resources."""
        if self._connection:
            try:
                self._conn.execute(f"DROP VIEW IF EXISTS {self._temp_view_name}")
                self.logger.debug("Cleaned up temporary view")
            except Exception as e:
                self.logger.warning(f"Failed to clean up temp resources: {e!s}")
