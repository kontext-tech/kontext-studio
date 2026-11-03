import logging
from typing import Any

from kontext.common.utils.datetime_utils import utc_now
from kontext.common.utils.sql_utils import (
    escape_sql_literal,
    generate_temp_view_name,
    parse_describe_nullability,
    quote_identifier,
)
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

from .models import ProfilerParameters, SchemaProfilingError, SchemaProfilingResult
from .profiler_base import SchemaProfilerBase
from .type_mapping import (
    is_numeric_type,
    is_text_type,
    map_duckdb_type_to_column_data_type,
)


class CsvSchemaProfiler(SchemaProfilerBase):
    """Schema profiler for CSV and delimited text files using DuckDB's
    built-in capabilities"""

    # Constants for consistency
    STATS_SOURCE_PRIMARY = "duckdb_desc"
    STATS_SOURCE_FALLBACK = "duckdb_desc"
    PROFILING_METHOD = "duckdb_csv"
    DEFAULT_ENCODING = "utf-8"

    def __init__(self, params: ProfilerParameters):
        super().__init__(params)
        self.logger = logging.getLogger(__name__)
        self._temp_view_name = generate_temp_view_name("temp_csv_view")

    def profile(self) -> SchemaProfilingResult:
        """Profile CSV file using DuckDB's built-in features for robust schema and
        statistics extraction"""
        try:
            self.logger.info(f"Starting CSV schema profiling for {self.storage_path}")

            if not self._connection:
                raise SchemaProfilingError("DuckDB connection not initialized")

            # Get CSV-specific parameters
            delimiter = self._get_delimiter()
            csv_options = self._get_csv_options()

            self.logger.debug(f"Using delimiter: '{delimiter}', options: {csv_options}")

            # Create temporary view for CSV file
            self._create_csv_view(delimiter, csv_options)

            # Extract schema using DuckDB's DESCRIBE
            schema_info = self._extract_schema_info()

            # Get row count and basic file info
            row_count = self._get_row_count()

            # Build file schema using generated API models
            file_schema = self._create_file_schema(schema_info, row_count, delimiter, csv_options)

            # Build file stats using generated API models
            file_stats = self._create_file_stats(schema_info, row_count)

            self.logger.info(
                f"Successfully profiled CSV file: {len(schema_info)} columns, {row_count} rows"
            )
            return SchemaProfilingResult.success_result(file_schema, file_stats)

        except Exception as e:
            error_msg = f"Failed to profile CSV file {self.storage_path}: {e!s}"
            self.logger.error(error_msg, exc_info=True)
            return SchemaProfilingResult.failure_result(error_msg, [error_msg])

        finally:
            self._cleanup_temp_resources()

    def _create_file_schema(
        self,
        schema_info: list[tuple],
        row_count: int,
        delimiter: str,
        csv_options: dict[str, Any],
    ) -> FileSchemaModel:
        """Create file schema using generated API model"""
        columns = []

        for col_name, col_type, col_nullable in schema_info:
            # Map DuckDB type to ColumnDataType enum
            data_type = map_duckdb_type_to_column_data_type(col_type)

            # Create Column model instance
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

        # Create file metadata using FileMetadata model
        metadata = FileMetadataModel(
            file_name=self.file_name,
            file_type=self.file_type,
            encoding=self.DEFAULT_ENCODING,
            compression_type=None,
            delimiter=delimiter,
            has_header=csv_options.get("header", True),
            format_specific_metadata=csv_options,
        )

        # Create file schema using FileSchema model with array-based structure
        table_name = self.file_name
        schema = FileSchemaModel(
            version="1.0",
            metadata=metadata,
            sub_schemas=[
                TableSchemaModel(
                    table_name=table_name,
                    columns=columns,
                    is_partitioned=False,
                    partition_columns=None,
                )
            ],
            last_modified=None,
            serde_info=None,
        )

        return schema

    def _create_file_stats(self, schema_info: list[tuple], row_count: int) -> FileStatsModel:
        """Create file stats using generated API model"""
        column_stats = []

        for col_name, col_type, _col_nullable in schema_info:
            # Get column statistics as ColumnStatsModel object
            column_stat = self._get_column_statistics(col_name, col_type)
            column_stats.append(column_stat)

        # Calculate overall null percentage
        total_nulls = sum(stats.null_count or 0 for stats in column_stats)
        total_cells = row_count * len(column_stats) if row_count and column_stats else 0
        null_percentage = total_nulls / total_cells if total_cells > 0 else 0.0

        # Create FileStats model instance with array-based structure
        # Use RFC 3339 UTC timestamp (with trailing 'Z') to satisfy validation regex
        table_name = self.file_name
        stats = FileStatsModel(
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
        )

        return stats

    def _get_column_statistics(self, col_name: str, col_type: str) -> ColumnStatsModel:
        """Get column statistics as ColumnStatsModel object"""
        try:
            if not self._connection:
                return ColumnStatsModel(column_name=col_name)

            assert self._connection is not None
            col_id = quote_identifier(col_name)

            # Get basic statistics
            null_count_query = f"""
                SELECT COUNT(*) as null_count
                FROM {self._temp_view_name}
                WHERE {col_id} IS NULL
            """
            null_result = self._connection.execute(null_count_query).fetchone()
            null_count = null_result[0] if null_result else 0

            # Get distinct count
            distinct_query = f"""
                SELECT COUNT(DISTINCT {col_id}) as distinct_count
                FROM {self._temp_view_name}
                WHERE {col_id} IS NOT NULL
            """
            distinct_result = self._connection.execute(distinct_query).fetchone()
            distinct_count = distinct_result[0] if distinct_result else 0

            # Get total count for completeness calculation
            total_query = f"""
                SELECT COUNT(*) as total_count
                FROM {self._temp_view_name}
            """
            total_result = self._connection.execute(total_query).fetchone()
            total_count = total_result[0] if total_result else 0

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
                        WHERE {col_id} IS NOT NULL AND {col_id} != ''
                    """
                    numeric_result = self._connection.execute(numeric_query).fetchone()
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
                    text_result = self._connection.execute(text_query).fetchone()
                    if text_result:
                        max_length = text_result[0]
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
                    top_values_result = self._connection.execute(top_values_query).fetchall()
                    if top_values_result:
                        top_values = {str(row[0]): row[1] for row in top_values_result}
                except Exception as e:
                    self.logger.warning(f"Failed to get top values for {col_name}: {e}")

            # Get raw samples
            samples = None
            try:
                samples_query = f"""
                    SELECT {col_id}
                    FROM {self._temp_view_name}
                    WHERE {col_id} IS NOT NULL
                    LIMIT {self.SAMPLES_LIMIT}
                """
                samples_result = self._connection.execute(samples_query).fetchall()
                if samples_result:
                    samples = [row[0] for row in samples_result]
            except Exception as e:
                self.logger.warning(f"Failed to get samples for {col_name}: {e}")

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
                samples=samples,
                true_count=None,
                false_count=None,
                true_ratio=None,
                stats_source=self.STATS_SOURCE_PRIMARY,
            )

        except Exception as e:
            self.logger.error(f"Error getting statistics for column {col_name}: {e!s}")
            return ColumnStatsModel(
                column_name=col_name,
                distinct_count=None,
                null_count=None,
                completeness_score=None,
            )

    def _get_delimiter(self) -> str:
        """Get the appropriate delimiter for the CSV file based on file type"""
        delimiter_map = {
            FileFormatType.CSV: ",",
            FileFormatType.TSV: "\t",
        }
        return delimiter_map.get(self.file_type, ",")

    def _get_csv_options(self) -> dict[str, Any]:
        """Get optimized CSV reading options for DuckDB read_csv function"""
        return {
            "header": True,  # Assume first row contains column headers
            "auto_detect": True,  # Enable automatic type and delimiter detection
            "sample_size": 50000,  # Large sample for accurate type detection
            "max_line_size": 1048576,  # 1MB max line size for robust parsing
            "ignore_errors": False,  # Fail fast on malformed data
            "null_padding": True,  # Handle missing values gracefully
            "all_varchar": False,  # Enable type detection (not all text)
            "normalize_names": False,  # Keep original column names
            "union_by_name": True,  # Union files by column name for consistency
        }

    def _create_csv_view(self, delimiter: str, csv_options: dict[str, Any]) -> None:
        """Create a temporary view of the CSV file for querying"""
        try:
            if not self._connection:
                raise SchemaProfilingError("DuckDB connection not initialized")

            assert self._connection is not None

            # Build the read_csv function call with options
            storage_path_lit = escape_sql_literal(self.storage_path)
            delimiter_lit = escape_sql_literal(delimiter)

            options_list = []
            for k, v in csv_options.items():
                if isinstance(v, str):
                    options_list.append(f"{k}={escape_sql_literal(v)}")
                elif isinstance(v, bool):
                    options_list.append(f"{k}={str(v).lower()}")
                else:
                    options_list.append(f"{k}={v}")

            options_str = ", ".join(options_list)

            create_view_sql = f"""
                CREATE OR REPLACE TEMP VIEW {self._temp_view_name} AS
                SELECT * FROM read_csv(
                    {storage_path_lit},
                    delim={delimiter_lit},
                    {options_str}
                )
            """

            self.logger.debug(f"Creating CSV view with SQL: {create_view_sql}")
            self._connection.execute(create_view_sql)

            # Verify the view was created successfully
            test_query = f"SELECT COUNT(*) FROM {self._temp_view_name}"
            result = self._connection.execute(test_query).fetchone()
            if result:
                self.logger.debug(f"CSV view created successfully with {result[0]} rows")

        except Exception as e:
            error_msg = f"Failed to create CSV view: {e!s}"
            self.logger.error(error_msg)
            raise SchemaProfilingError(error_msg) from e

    def _extract_schema_info(self) -> list[tuple[str, str, str]]:
        """Extract schema information using DuckDB's DESCRIBE command"""
        try:
            assert self._connection is not None
            describe_query = f"DESCRIBE {self._temp_view_name}"
            self.logger.debug(f"Executing schema extraction: {describe_query}")

            result = self._connection.execute(describe_query).fetchall()
            schema_info = [(row[0], row[1], row[2]) for row in result]

            self.logger.debug(f"Extracted schema info for {len(schema_info)} columns")
            return schema_info

        except Exception as e:
            error_msg = f"Failed to extract schema information: {e!s}"
            self.logger.error(error_msg)
            raise SchemaProfilingError(error_msg) from e

    def _get_row_count(self) -> int:
        """Get the total number of rows in the CSV file"""
        try:
            assert self._connection is not None
            count_query = f"SELECT COUNT(*) FROM {self._temp_view_name}"
            result = self._connection.execute(count_query).fetchone()
            row_count = result[0] if result else 0

            self.logger.debug(f"CSV file contains {row_count} rows")
            return row_count

        except Exception as e:
            self.logger.warning(f"Failed to get row count: {e!s}")
            return 0

    def _cleanup_temp_resources(self) -> None:
        """Clean up temporary resources created during profiling"""
        try:
            if self._connection:
                # Drop the temporary view if it exists
                cleanup_sql = f"DROP VIEW IF EXISTS {self._temp_view_name}"
                self._connection.execute(cleanup_sql)
                self.logger.debug("Cleaned up temporary CSV view")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup temporary resources: {e!s}")
