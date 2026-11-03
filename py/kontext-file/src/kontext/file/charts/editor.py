"""
ChartEditor - Manages standalone .chart files.

This editor wraps the ChartDocument model and provides methods for creating,
updating, and manipulating chart files, similar to how NotebookEditor manages
notebook blocks.
"""

import logging
from datetime import UTC, datetime
from uuid import uuid4

from kontext.common.artifacts.provenance import flatten_provenance_metadata
from kontext.common.artifacts.sequencing import MonotonicActionSequencer
from kontext.common.protocols import IFileServiceProtocol
from kontext.schema import (
    ArtifactAction,
    ArtifactProvenance,
    ChartConfig,
    ChartDocument,
    ChartDocumentMetadata,
    ChartUpdateConfigAction,
    ChartUpdateConfigActionPayload,
    DataRef,
    DataTableSummary,
    InlineData,
)


class ChartEditor:
    """
    Editor class for creating and manipulating standalone ChartDocument instances.

    Provides methods for:
    - Creating new chart documents
    - Managing metadata
    - Swapping between embedded data tables and data references
    - Updating chart configurations
    """

    def __init__(
        self,
        chart: ChartDocument | None = None,
        file_service: IFileServiceProtocol | None = None,
        logger: logging.Logger | None = None,
        project_id: str | None = None,
        file_id: str | None = None,
    ):
        """
        Initialize the editor with an existing chart or create a new one.

        Args:
            chart: Existing ChartDocument to manage, or None for factory methods
            file_service: FileService instance for API operations
            logger: Custom logger instance, defaults to module logger if None
            project_id: Optional project ID for data-table fetching and validation
            file_id: File ID for loaded charts
                (filesystem identity, separate from document content)
        """
        self.logger = logger or logging.getLogger(__name__)
        self.chart = chart
        self.file_service = file_service
        self.project_id = project_id
        self._file_id = file_id  # Track file ID separately from document content
        self._data_table_cache: dict[str, InlineData] = {}
        self._loaded_from_service = chart is not None

        # Action tracking for granular streaming
        # Use high-precision monotonically increasing sequence (microseconds)
        self._action_sequencer = MonotonicActionSequencer()
        self._pending_actions: list[ArtifactAction] = []

    async def load_chart_from_file(self, project_id: str, chart_id: str) -> ChartDocument:
        """
        Load an existing chart from the file service.

        Returns:
            The loaded ChartDocument
        """
        if not self.file_service:
            raise ValueError("File service is not available")

        self.logger.info(f"Loading chart: {chart_id}")
        content = await self.file_service.get_file_content(project_id, chart_id)
        self.chart = ChartDocument.model_validate_json(content)
        self._file_id = chart_id  # Store file ID separately from document
        self._loaded_from_service = True

        # Clear any pending actions from previous operations
        self._pending_actions = []

        return self.chart

    def take_actions(self) -> list[ArtifactAction]:
        """Return and clear pending actions for streaming."""
        actions = self._pending_actions
        self._pending_actions = []
        return actions

    def _next_action_sequence(self) -> int:
        """Get the next sequence number and increment."""
        return self._action_sequencer.next()

    def create_chart(
        self,
        name: str,
        config: ChartConfig,
        data_ref: DataRef | None = None,
        inline_data: InlineData | None = None,
        description: str | None = None,
        chart_id: str | None = None,
        data_summary: DataTableSummary | None = None,
        notebook_id: str | None = None,
        query_session_id: str | None = None,
        chat_session_id: str | None = None,
        provenance: ArtifactProvenance | None = None,
    ) -> ChartDocument:
        """
        Create a new chart document.

        Args:
            name: Name of the chart
            config: Chart configuration (type, mappings, etc.)
            data_ref: Optional reference to an external data table
            inline_data: Optional embedded data table
            description: Optional description
            chart_id: Optional chart ID (generates UUID if not provided)
            data_summary: Optional data summary
            notebook_id: Optional notebook file ID that owns this chart
            query_session_id: Optional query session ID behind the data
            chat_session_id: Optional AI chat session ID that generated the chart
            provenance: Optional organizational provenance flattened into metadata

        Returns:
            New ChartDocument instance
        """
        now = datetime.now(UTC)
        chart_id = chart_id or str(uuid4())

        metadata = ChartDocumentMetadata(
            description=description,
            created_at=now,
            modified_at=now,
            version="1.0.0",
            notebook_id=notebook_id,
            query_session_id=query_session_id,
            chat_session_id=chat_session_id,
        )
        flatten_provenance_metadata(metadata, provenance)

        # Populate summary if missing but data is present
        if not data_summary and (inline_data or data_ref):
            ds_id = data_ref.data_id if data_ref else None

            if inline_data and inline_data.table:
                first_table = inline_data.table
                # Try explicit row count first, then calculate from rows
                if first_table.row_count is not None:
                    row_cnt = first_table.row_count
                else:
                    row_cnt = len(first_table.rows or [])

                data_summary = DataTableSummary(
                    columns=first_table.columns or [], row_count=row_cnt, data_id=ds_id
                )

        chart_doc = ChartDocument(
            name=name,
            config=config,
            data_ref=data_ref,
            inline_data=inline_data,
            metadata=metadata,
            data_summary=data_summary,
        )

        self.chart = chart_doc
        self._file_id = chart_id  # Store file ID separately
        return chart_doc

    def load_chart(self, chart: ChartDocument) -> None:
        """Load an existing chart document for management."""
        self.chart = chart

    def get_chart(self) -> ChartDocument | None:
        """Get the current chart document."""
        return self.chart

    def update_name(self, name: str) -> None:
        """Update the chart name."""
        if not self.chart:
            raise ValueError("No chart loaded")
        self.chart.name = name
        self._update_modified()

    def update_config(self, config: ChartConfig) -> None:
        """Update the chart configuration."""
        if not self.chart:
            raise ValueError("No chart loaded")
        self.chart.config = config
        self._update_modified()

        # Emit action for frontend reload/refresh
        # We use a broad path to trigger a full refresh of the chart component
        self._pending_actions.append(
            ArtifactAction(
                root=ChartUpdateConfigAction(
                    sequence=self._next_action_sequence(),
                    action_type="updateChartConfig",
                    payload=ChartUpdateConfigActionPayload(
                        config_path=[],  # Empty path indicates root config update
                        value=config.model_dump(by_alias=True),
                    ),
                )
            )
        )

    def set_data_ref(self, data_ref: DataRef, clear_embedded: bool = True) -> None:
        """
        Set a reference to an external data table.

        This is typically used for larger result sets or SQL query outputs.
        """
        if not self.chart:
            raise ValueError("No chart loaded")
        self.chart.data_ref = data_ref
        # Optionally clear embedded data to keep file lightweight
        if clear_embedded:
            self.chart.inline_data = None
        self._update_modified()

    def set_embedded_data(self, inline_data: InlineData) -> None:
        """
        Set embedded data directly in the chart.

        This is typically used for small, static, or LLM-generated data tables.
        Embedded data takes priority over dataRef during rendering.
        """
        if not self.chart:
            raise ValueError("No chart loaded")
        self.chart.inline_data = inline_data
        self._update_modified()

    def clear_data_ref(self) -> None:
        """Clear the external data-table reference."""
        if not self.chart:
            raise ValueError("No chart loaded")
        self.chart.data_ref = None
        self._update_modified()

    def clear_embedded_data(self) -> None:
        """Clear the embedded data."""
        if not self.chart:
            raise ValueError("No chart loaded")
        self.chart.inline_data = None
        self._update_modified()

    def update_metadata(self, **kwargs) -> None:
        """
        Update metadata attributes.

        Pass keyword arguments for fields to update (e.g., description).
        """
        if not self.chart:
            raise ValueError("No chart loaded")

        if self.chart.metadata is None:
            now = datetime.now(UTC)
            self.chart.metadata = ChartDocumentMetadata(
                description=None, created_at=now, modified_at=now, version="1.0.0"
            )

        for key, value in kwargs.items():
            if hasattr(self.chart.metadata, key):
                setattr(self.chart.metadata, key, value)

        self._update_modified()

    def get_metadata(self) -> ChartDocumentMetadata | None:
        """Get the current metadata."""
        if not self.chart:
            return None
        return self.chart.metadata

    def has_embedded_data(self) -> bool:
        """Check if the chart has embedded data."""
        return self.chart is not None and self.chart.inline_data is not None

    def has_data_ref(self) -> bool:
        """Check if the chart has a data-table reference."""
        return self.chart is not None and self.chart.data_ref is not None

    def _update_modified(self) -> None:
        """Update the modified timestamp in metadata."""
        if self.chart and self.chart.metadata:
            self.chart.metadata.modified_at = datetime.now(UTC)

    async def save_chart(self, project_id: str | None = None) -> None:
        """
        Save the chart to the file service.

        Args:
            project_id: Project ID (uses instance project_id if not provided)

        Raises:
            ValueError: If file_service is not provided or chart is not loaded
        """
        if not self.file_service:
            raise ValueError("FileService not provided. Cannot save chart.")

        if not self.chart:
            raise ValueError("No chart loaded. Cannot save.")

        project_id = project_id or self.project_id
        if not project_id:
            raise ValueError("Project ID is required to save chart.")

        # Determine if this is create or update
        if self._loaded_from_service and self._file_id:
            self.logger.info(f"Updating existing chart: {self._file_id}")
            await self.file_service.update_chart(
                project_id=project_id,
                file_id=self._file_id,
                chart=self.chart,
                name=self.chart.name,
            )
        else:
            self.logger.info("Creating new chart")
            metadata = self.chart.metadata
            response = await self.file_service.create_chart(
                project_id=project_id,
                chart=self.chart,
                name=self.chart.name,
                notebook_id=metadata.notebook_id if metadata else None,
                query_session_id=metadata.query_session_id if metadata else None,
                chat_session_id=metadata.chat_session_id if metadata else None,
            )
            # Store the file ID returned by the backend
            if response and response.file:
                self._file_id = response.file.id
                self._loaded_from_service = True

    def validate_chart(self) -> list[str]:
        """
        Validate the current chart.

        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []

        if not self.chart:
            errors.append("No chart loaded")
            return errors

        if not self.chart.name or len(self.chart.name.strip()) == 0:
            errors.append("Chart name is required")

        if not self.chart.config:
            errors.append("Chart configuration is required")

        if not self.has_embedded_data() and not self.has_data_ref():
            errors.append("Chart must have either embedded data or a data-table reference")

        return errors
