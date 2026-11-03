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


class ParquetSchemaProfiler(SchemaProfilerBase):
    """Schema profiler for Parquet files using DuckDB's built-in capabilities"""

    # Constants for consistency
    STATS_SOURCE_PRIMARY = "duckdb_desc"
    PROFILING_METHOD = "duckdb_pq"

    def __init__(self, params: ProfilerParameters):
        super().__init__(params)
        self.logger = logging.getLogger(__name__)
        self._temp_view_name = generate_temp_view_name("temp_parquet_view")

    def profile(self) -> SchemaProfilingResult:
        """Profile Parquet file using DuckDB's built-in features"""
        try:
            self.logger.info(f"Starting Parquet schema profiling for {self.storage_path}")

            if not self._connection:
                raise SchemaProfilingError("DuckDB connection not initialized")

            # Create temporary view for Parquet file
            self._create_parquet_view()

            # Extract schema using DuckDB's DESCRIBE
            schema_info = self._extract_schema_info()

            # Get row count
            row_count = self._get_row_count()

            # Get Parquet-specific metadata
            parquet_metadata = self._get_parquet_metadata()

            # Build file schema and stats using generated API models
            file_schema = self._create_file_schema(schema_info, row_count, parquet_metadata)
            file_stats = self._create_file_stats(schema_info, row_count)

            self.logger.info(
                f"Successfully profiled Parquet file: {len(schema_info)} columns, {row_count} rows"
            )
            return SchemaProfilingResult.success_result(file_schema, file_stats)

        except Exception as e:
            error_msg = f"Failed to profile Parquet file {self.storage_path}: {e!s}"
            self.logger.error(error_msg, exc_info=True)
            return SchemaProfilingResult.failure_result(error_msg, [error_msg])

        finally:
            self._cleanup_temp_resources()

    def _create_file_schema(
        self, schema_info: list[tuple], row_count: int, parquet_metadata: dict[str, Any]
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
            encoding=None,
            compression_type=parquet_metadata.get("compression"),
            delimiter=None,
            has_header=None,
            format_specific_metadata=parquet_metadata,
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
        """Get column statistics using Parquet metadata when available,
        fallback to SQL queries
        """
        try:
            if not self._connection:
                return ColumnStatsModel(column_name=col_name)

            assert self._connection is not None

            # First try to get statistics from parquet_metadata
            # (more efficient and accurate)
            parquet_stats = self._get_parquet_column_stats(col_name)
            if parquet_stats:
                return parquet_stats

            # Fallback to SQL-based statistics if parquet metadata is unavailable
            return self._get_sql_column_stats(col_name, col_type)

        except Exception as e:
            self.logger.error(f"Error getting statistics for column {col_name}: {e!s}")
            return ColumnStatsModel(column_name=col_name)

    def _get_parquet_column_stats(self, col_name: str) -> ColumnStatsModel | None:
        """Get column statistics from parquet_metadata() - more efficient
        and accurate"""
        try:
            assert self._connection is not None

            # Get column metadata from parquet_metadata
            parquet_stats_query = f"""
                SELECT
                    path_in_schema,
                    type,
                    stats_min,
                    stats_max,
                    stats_null_count,
                    stats_distinct_count,
                    num_values,
                    compression,
                    encodings
                FROM parquet_metadata({escape_sql_literal(self.storage_path)})
                WHERE path_in_schema = {escape_sql_literal(col_name)}
                LIMIT 1
            """

            result = self._connection.execute(parquet_stats_query).fetchone()
            if result:
                (
                    _path,
                    data_type,
                    stats_min,
                    stats_max,
                    null_count,
                    distinct_count,
                    num_values,
                    _compression,
                    _encodings,
                ) = result

                # Calculate completeness score
                completeness_score = (
                    (num_values - (null_count or 0)) / num_values
                    if num_values and num_values > 0
                    else 0.0
                )

                # Convert string stats to appropriate types for numeric columns
                min_value = self._convert_stat_value(stats_min, data_type)
                max_value = self._convert_stat_value(stats_max, data_type)

                return ColumnStatsModel(
                    column_name=col_name,
                    distinct_count=distinct_count,
                    null_count=null_count,
                    completeness_score=completeness_score,
                    min_value=min_value,
                    max_value=max_value,
                    std_dev=None,  # Not available in parquet metadata
                    median_value=None,  # Not available in parquet metadata
                    avg_value=None,  # Not available in parquet metadata
                    max_length=None,  # Could be calculated for string types
                    top_values=None,  # Not available in parquet metadata
                    true_count=None,
                    false_count=None,
                    true_ratio=None,
                    stats_source="duckdb_pq_meta",
                )

            return None

        except Exception as e:
            self.logger.warning(f"Failed to get parquet column stats for {col_name}: {e}")
            return None

    def _get_sql_column_stats(self, col_name: str, col_type: str) -> ColumnStatsModel:
        """Fallback method: Get column statistics using SQL queries"""
        try:
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

                # Initialize with basic stats
                min_value = None
                max_value = None
                avg_value = None
                std_dev = None
                max_length = None
                top_values = None

                # Add numeric statistics if applicable
                if is_numeric_type(col_type):
                    try:
                        numeric_query = f"""
                            SELECT
                                MIN({col_id}) as min_val,
                                MAX({col_id} ) as max_val,
                                AVG({col_id}) as avg_val,
                                STDDEV({col_id}) as std_dev
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

                # Get top values for categorical data (both numeric and text)
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

            return ColumnStatsModel(column_name=col_name, stats_source="no_data")

        except Exception as e:
            self.logger.warning(f"Failed to get SQL column stats for {col_name}: {e}")
            return ColumnStatsModel(column_name=col_name)

    def _convert_stat_value(self, value_str: str | None, parquet_type: str) -> Any:
        """Convert string statistics values to appropriate Python types"""
        if value_str is None:
            return None

        # Handle NA values - return None for any NA-like value, including empty strings
        na_values = {"NA", "N/A", "null", "NULL", "None", "", "nan", "NaN", "NAN"}
        if value_str in na_values:
            return None

        # BYTE_ARRAY type in Parquet is used for strings and binary data
        # We should never try to convert these to numeric values for min/max
        if parquet_type in (
            "BOOLEAN",
            "VARCHAR",
            "STRING",
            "CHAR",
            "ENUM",
            "BYTE_ARRAY",
        ):
            # For non-numeric columns, return None instead of text values
            # This matches our model expectations for minValue/maxValue
            return None

        # Handle common boolean-like string values that might appear in data
        boolean_values = {"true", "false", "yes", "no", "y", "n", "t", "f"}
        if value_str.lower() in boolean_values:
            # Boolean values should not be treated as numeric
            return None

        try:
            # For numeric types, try to convert to appropriate type
            if parquet_type in ("INT32", "INT64", "BIGINT"):
                # Try to handle values like "1.0" that should be integers
                float_val = float(value_str)
                if float_val.is_integer():
                    return int(float_val)
                return float_val  # Return as float if it's not a clean integer
            elif parquet_type in ("FLOAT", "DOUBLE", "FIXED_LEN_BYTE_ARRAY", "DECIMAL"):
                return float(value_str)
            else:
                # For any other type, we'll attempt numeric conversion
                # If it looks like a number, convert it
                if value_str.replace(".", "", 1).replace("-", "", 1).isdigit():
                    # If it has a decimal point, convert to float, otherwise int
                    return float(value_str) if "." in value_str else int(value_str)
                # Otherwise return None instead of a string to avoid validation errors
                return None
        except (ValueError, TypeError):
            # If conversion fails, return None instead of string to avoid
            # validation errors
            self.logger.debug(
                f"Could not convert value '{value_str}' to numeric type, returning None"
            )
            return None

    def _create_parquet_view(self) -> None:
        """Create a temporary view of the Parquet file for querying"""
        try:
            if not self._connection:
                raise SchemaProfilingError("DuckDB connection not initialized")

            assert self._connection is not None

            # Create the temporary view
            create_view_sql = f"""
                CREATE OR REPLACE TEMP VIEW {self._temp_view_name} AS
                SELECT * FROM parquet_scan({escape_sql_literal(self.storage_path)})
            """

            self.logger.debug(f"Creating Parquet view with SQL: {create_view_sql}")
            self._connection.execute(create_view_sql)

        except Exception as e:
            error_msg = f"Failed to create Parquet view: {e!s}"
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

    def _get_parquet_metadata(self) -> dict[str, Any]:
        """Get Parquet-specific file-level metadata using parquet_file_metadata()"""
        metadata = {}

        try:
            assert self._connection is not None

            # Get file-level metadata using parquet_file_metadata (one row per file)
            file_metadata_query = (
                f"SELECT * FROM parquet_file_metadata('{self.storage_path}') LIMIT 1"
            )
            result = self._connection.execute(file_metadata_query).fetchone()

            if result:
                # Get column names from the query description
                description = self._connection.description
                if description:
                    columns = [desc[0] for desc in description]

                    # Map column names to values
                    for i, column_name in enumerate(columns):
                        if i < len(result):
                            metadata[column_name] = result[i]

                    self.logger.debug(
                        f"Retrieved parquet file metadata with {len(metadata)} fields"
                    )
                else:
                    self.logger.warning("No column description available for parquet file metadata")
            else:
                self.logger.warning("No parquet file metadata returned")

        except Exception as e:
            self.logger.warning(f"Failed to get Parquet file metadata: {e!s}")

        return metadata

    def _cleanup_temp_resources(self) -> None:
        """Clean up temporary resources"""
        try:
            if self._connection:
                cleanup_sql = f"DROP VIEW IF EXISTS {self._temp_view_name}"
                self._connection.execute(cleanup_sql)
                self.logger.debug("Cleaned up temporary Parquet view")
        except Exception as e:
            self.logger.warning(f"Failed to cleanup temporary resources: {e!s}")
