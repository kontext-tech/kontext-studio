"""Helpers for converting persisted chat attachment context into runtime state."""

from __future__ import annotations

from collections import defaultdict

from kontext.schema import (
    AttachedDataSource,
    AttachedDataTable,
    ChatAttachmentContext,
)

_ATTACHED_DATA_SUMMARY_COLUMN_LIMIT = 8


def build_attached_data_sources(
    context: ChatAttachmentContext | None,
) -> list[AttachedDataSource]:
    """Group persisted file/table mappings into runtime attached-data sources."""
    if context is None:
        return []

    tables_by_file_id: dict[str, list[AttachedDataTable]] = defaultdict(list)
    for table in context.tables:
        tables_by_file_id[table.file_id].append(
            AttachedDataTable(
                entity_id=table.entity_id,
                namespace_name=table.namespace_name,
                entity_name=table.entity_name,
                row_count=table.row_count,
                column_names=table.column_names,
            )
        )

    sources: list[AttachedDataSource] = []
    for file in context.files:
        tables = sorted(
            tables_by_file_id.get(file.file_id, []),
            key=lambda table: (table.namespace_name.lower(), table.entity_name.lower()),
        )
        sources.append(
            AttachedDataSource(
                file_id=file.file_id,
                file_name=file.file_name,
                file_type=file.file_type,
                tables=tables,
            )
        )

    return sorted(sources, key=lambda source: source.file_name.lower())


def build_attached_data_summary(
    attached_data_sources: list[AttachedDataSource],
) -> str | None:
    """Build a compact prompt summary for attached data sources."""
    if not attached_data_sources:
        return None

    lines: list[str] = []
    for source in attached_data_sources:
        table_summaries: list[str] = []
        for table in source.tables:
            column_names = table.column_names[:_ATTACHED_DATA_SUMMARY_COLUMN_LIMIT]
            remaining_columns = max(
                len(table.column_names) - _ATTACHED_DATA_SUMMARY_COLUMN_LIMIT,
                0,
            )
            columns_summary = ", ".join(column_names)
            if remaining_columns > 0:
                columns_summary = (
                    f"{columns_summary}, +{remaining_columns} more"
                    if columns_summary
                    else f"+{remaining_columns} more"
                )

            table_summary = f"`{table.namespace_name}.{table.entity_name}`"
            if table.row_count is not None:
                table_summary = f"{table_summary} ({table.row_count} rows)"
            if columns_summary:
                table_summary = f"{table_summary}: {columns_summary}"
            table_summaries.append(table_summary)

        if table_summaries:
            lines.append(f"`{source.file_name}` -> {'; '.join(table_summaries)}")
        else:
            lines.append(f"`{source.file_name}` -> no resolved tables")

    return "\n".join(lines)
