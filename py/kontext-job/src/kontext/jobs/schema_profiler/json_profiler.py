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


class JsonSchemaProfiler(SchemaProfilerBase):
    """Schema profiler for JSON and JSONL files using DuckDB's built-in capabilities"""

    # Constants for consistency
    STATS_SOURCE_PRIMARY = "duckdb_desc"
    PROFILING_METHOD = "duckdb_json"
    DEFAULT_ENCODING = "utf-8"

    def __init__(self, params: ProfilerParameters):
        super().__init__(params)
        self.logger = logging.getLogger(__name__)
        self._temp_view_name = generate_temp_view_name("temp_json_view")

    def profile(self) -> SchemaProfilingResult:
        """Profile JSON/JSONL file using DuckDB's built-in features"""
        try:
            self.logger.info(f"Starting JSON schema profiling for {self.storage_path}")

            if not self._connection:
                raise SchemaProfilingError("DuckDB connection not initialized")

            # Type assertion for better static analysis
            assert self._connection is not None

            # Get JSON-specific parameters
            json_options = self._get_json_options()

            # Create temporary view for JSON file
            self._create_json_view(json_options)

            # Extract schema using DuckDB's DESCRIBE
            schema_info = self._extract_schema_info()

            # Get row count
            row_count = self._get_row_count()

            # Build file schema and stats using generated API models
            file_schema = self._create_file_schema(schema_info, row_count, json_options)
            file_stats = self._create_file_stats(schema_info, row_count)

            self.logger.info(
                f"Successfully profiled JSON file: {len(schema_info)} columns, {row_count} rows"
            )
            return SchemaProfilingResult.success_result(file_schema, file_stats)

        except Exception as e:
            error_msg = f"Failed to profile JSON file {self.storage_path}: {e!s}"
            self.logger.error(error_msg, exc_info=True)
            return SchemaProfilingResult.failure_result(error_msg, [error_msg])

        finally:
            self._cleanup_temp_resources()

    def _create_file_schema(
        self, schema_info: list[tuple], row_count: int, json_options: dict[str, Any]
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
            delimiter=None,
            has_header=None,
            format_specific_metadata=json_options,
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
        """Create file stats dictionary using generated API model structure"""
        column_stats = []

        for col_name, col_type, _col_nullable in schema_info:
            # Get column statistics as ColumnStats object
            column_stat = self._get_column_statistics(col_name, col_type)
            column_stats.append(column_stat)

        # Calculate overall null percentage
        total_nulls = sum(stats.null_count or 0 for stats in column_stats)
        total_cells = row_count * len(column_stats) if row_count and column_stats else 0
        null_percentage = total_nulls / total_cells if total_cells > 0 else 0.0

        # Create FileStats model instance with array-based structure
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
        )

        return stats

    def _get_column_statistics(self, col_name: str, col_type: str) -> ColumnStatsModel:
        """Get basic column statistics as ColumnStats object"""
        try:
            if not self._connection:
                return ColumnStatsModel(column_name=col_name)

            assert self._connection is not None
            col_id = quote_identifier(col_name)

            # Get basic statistics
            basic_stats_query = f"""
                SELECT
                    COUNT(DISTINCT {col_id}) as distinct_count,
                    COUNT(*) - COUNT({col_id}) as null_count,
                    COUNT(*) as total_count
                FROM {self._temp_view_name}
            """

            result = self._connection.execute(basic_stats_query).fetchone()
            if result:
                distinct_count, null_count, total_count = result
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

            return ColumnStatsModel(column_name=col_name, stats_source="no_data")

        except Exception as e:
            self.logger.error(f"Error getting statistics for column {col_name}: {e!s}")
            return ColumnStatsModel(column_name=col_name)

    def _get_json_options(self) -> dict[str, Any]:
        """Get JSON reading options for DuckDB"""
        # Different options for JSON vs JSONL
        if self.file_type == FileFormatType.JSONL:
            return {
                "format": "newline_delimited",
                "auto_detect": True,
                "sample_size": 50000,
                "maximum_depth": 10,
            }
        else:
            return {
                "format": "auto",
                "auto_detect": True,
                "sample_size": 50000,
                "maximum_depth": 10,
            }

    def _create_json_view(self, json_options: dict[str, Any]) -> None:
        """Create a temporary view of the JSON file for querying"""
        try:
            if not self._connection:
                raise SchemaProfilingError("DuckDB connection not initialized")

            assert self._connection is not None

            # Build the read_json function call with options
            storage_path_lit = escape_sql_literal(self.storage_path)
            options_list = []
            for k, v in json_options.items():
                if isinstance(v, str):
                    options_list.append(f"{k}={escape_sql_literal(v)}")
                elif isinstance(v, bool):
                    options_list.append(f"{k}={str(v).lower()}")
                else:
                    options_list.append(f"{k}={v}")

            options_str = ", ".join(options_list)

            create_view_sql = f"""
                CREATE OR REPLACE TEMP VIEW {self._temp_view_name} AS
                SELECT * FROM read_json(
                    {storage_path_lit},
                    {options_str}
                )
            """

            self.logger.debug(f"Creating JSON view with SQL: {create_view_sql}")
            self._connection.execute(create_view_sql)

        except Exception as e:
            error_msg = f"Failed to create JSON view: {e!s}"
            self.logger.error(error_msg)
            raise SchemaProfilingError(error_msg) from e

    def _extract_schema_info(self) -> list[tuple[str, str, str]]:
        """Extract schema information using DuckDB's DESCRIBE command"""
        try:
            assert self._connection is not None
            describe_query = f"DESCRIBE {self._temp_view_name}"
            result = self._connection.execute(describe_query).fetchall()
            schema_info = [(row[0], row[1], row[2]) for row in result]
            return schema_info

        except Exception as e:
            error_msg = f"Failed to extract schema information: {e!s}"
            self.logger.error(error_msg)
            raise SchemaProfilingError(error_msg) from e

    def _get_row_count(self) -> int:
        """Get the total number of rows"""
        try:
            assert self._connection is not None
            count_query = f"SELECT COUNT(*) FROM {self._temp_view_name}"
            result = self._connection.execute(count_query).fetchone()
            return result[0] if result else 0

        except Exception as e:
            self.logger.warning(f"Failed to get row count: {e!s}")
            return 0

    def _cleanup_temp_resources(self) -> None:
        """Clean up temporary resources"""
        try:
            if self._connection:
                cleanup_sql = f"DROP VIEW IF EXISTS {self._temp_view_name}"
                self._connection.execute(cleanup_sql)
                self.logger.debug("Cleaned up temporary JSON view")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup temporary resources: {e!s}")
