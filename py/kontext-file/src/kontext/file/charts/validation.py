"""
Chart field validation service - shared validation logic for chart creation.

This service provides validation utilities for chart configurations,
ensuring that field references (x_field, y_field, etc.) exist in data tables.
"""

from kontext.schema import (
    ChartConfig,
    DataColumn,
    DataTable,
    DataTableSummary,
    InlineData,
)


class ChartFieldValidator:
    """Centralized chart field validation service."""

    @staticmethod
    def extract_field_names_from_config(
        config: ChartConfig,
    ) -> dict[str, str | list[str] | None]:
        """Extract all field names from a chart configuration.

        Args:
            config: Chart configuration to extract fields from

        Returns:
            Dictionary mapping field types to field names
            Example: {'x_field': 'date', 'y_field': 'sales', 'color_field': 'region'}
        """
        config_root = config.root
        field_names: dict[str, str | list[str] | None] = {}

        # Common fields for most chart types - use getattr to safely access
        if x_field := getattr(config_root, "x_field", None):
            field_names["x_field"] = x_field
        if y_field := getattr(config_root, "y_field", None):
            field_names["y_field"] = y_field
        if bin_field := getattr(config_root, "bin_field", None):
            field_names["bin_field"] = bin_field
        if color_field := getattr(config_root, "color_field", None):
            field_names["color_field"] = color_field
        if size_field := getattr(config_root, "size_field", None):
            field_names["size_field"] = size_field

        # Pie chart specific fields
        if angle_field := getattr(config_root, "angle_field", None):
            field_names["angle_field"] = angle_field

        # Dual axes and funnel specific fields
        if left_y_field := getattr(config_root, "left_y_field", None):
            field_names["left_y_field"] = left_y_field
        if right_y_field := getattr(config_root, "right_y_field", None):
            field_names["right_y_field"] = right_y_field
        if left_color_field := getattr(config_root, "left_color_field", None):
            field_names["left_color_field"] = left_color_field
        if right_color_field := getattr(config_root, "right_color_field", None):
            field_names["right_color_field"] = right_color_field
        if compare_field := getattr(config_root, "compare_field", None):
            field_names["compare_field"] = compare_field
        if series_field := getattr(config_root, "series_field", None):
            field_names["series_field"] = series_field

        # Heatmap specific fields
        if x_axis_field := getattr(config_root, "x_axis_field", None):
            field_names["x_axis_field"] = x_axis_field
        if y_axis_field := getattr(config_root, "y_axis_field", None):
            field_names["y_axis_field"] = y_axis_field
        if value_field := getattr(config_root, "value_field", None):
            field_names["value_field"] = value_field
        if shape_field := getattr(config_root, "shape_field", None):
            field_names["shape_field"] = shape_field

        return field_names

    @staticmethod
    def get_column_names_from_data_table(
        inline_data: InlineData | None = None,
        data_table: DataTable | None = None,
        data_table_summary: DataTableSummary | None = None,
    ) -> list[str]:
        """Extract column names from various data-table formats.

        Args:
            inline_data: Optional inline data with embedded tables
            data_table: Optional single data table
            data_table_summary: Optional data table summary

        Returns:
            List of column names available in the data table
        """
        # Try to get columns from embedded data table
        if inline_data and inline_data.table:
            table = inline_data.table
            if table.columns:
                return [col.name for col in table.columns]

        # Try to get columns from single data table
        if data_table and data_table.columns:
            return [col.name for col in data_table.columns]

        # Try to get columns from data table summary
        if data_table_summary and data_table_summary.columns:
            return [col.name for col in data_table_summary.columns]

        return []

    @staticmethod
    def get_column_names_from_columns(columns: list[DataColumn] | None) -> list[str]:
        """Extract column names from a list of DataColumn objects.

        Args:
            columns: List of DataColumn objects

        Returns:
            List of column names
        """
        if not columns:
            return []
        return [col.name for col in columns]

    @staticmethod
    def validate_fields(
        field_names: dict[str, str | list[str] | None],
        available_columns: list[str],
        context_name: str,
    ) -> None:
        """Validate that all specified field names exist in available columns.

        Args:
            field_names: Dictionary of field_type -> field_name
                        Example: {'x_field': 'date', 'y_field': 'sales'}
            available_columns: List of available column names from the data table
            context_name: Name of chart/context being validated (for error messages)

        Raises:
            ValueError: If any field does not exist in available columns with
                       detailed error message listing missing fields and
                       available columns
        """
        if not available_columns:
            # Allow validation to pass if no columns available
            # (could be lazy-loaded data)
            return

        missing_fields = []
        for field_type, field_name in field_names.items():
            if isinstance(field_name, list):
                for index, item in enumerate(field_name):
                    if item and item not in available_columns:
                        missing_fields.append(f"{field_type}[{index}]='{item}'")
                continue

            if field_name and field_name not in available_columns:
                missing_fields.append(f"{field_type}='{field_name}'")

        if missing_fields:
            error_msg = (
                f"Invalid chart configuration for '{context_name}': "
                f"fields {', '.join(missing_fields)} do not exist in the data table. "
                f"Available columns: {', '.join(available_columns)}"
            )
            raise ValueError(error_msg)

    @staticmethod
    def validate_config_against_data_table(
        config: ChartConfig,
        inline_data: InlineData | None = None,
        data_table: DataTable | None = None,
        data_table_summary: DataTableSummary | None = None,
        context_name: str = "chart",
    ) -> None:
        """Validate a chart config against a data table in one call.

        Convenience method that combines field extraction, column extraction,
        and validation.

        Args:
            config: Chart configuration to validate
            inline_data: Optional inline data with embedded tables
            data_table: Optional single data table
            data_table_summary: Optional data table summary
            context_name: Name of chart/context being validated (for error messages)

        Raises:
            ValueError: If validation fails with detailed error message
        """
        field_names = ChartFieldValidator.extract_field_names_from_config(config)
        available_columns = ChartFieldValidator.get_column_names_from_data_table(
            inline_data=inline_data,
            data_table=data_table,
            data_table_summary=data_table_summary,
        )
        ChartFieldValidator.validate_fields(field_names, available_columns, context_name)
