from __future__ import annotations

import json
import logging
import time
from typing import Any, Literal, cast
from uuid import uuid4

from kontext.common.artifacts.sequencing import MonotonicActionSequencer
from kontext.common.notebook_aliases import normalize_sql_aliases
from kontext.common.protocols import IFileServiceProtocol, IQuerySessionServiceProtocol
from kontext.schema import (
    ArtifactAction,
    BlockData,
    BoxChartType,
    ChartBlock,
    ChartConfig,
    ChartSpec,
    CodeBlock,
    CodeBlockData,
    CodeExecutionOutput,
    DataRef,
    DualAxesChartType,
    FileModel,
    FileUploadResponse,
    InlineData,
    MarkTypes,
    NotebookBlock,
    NotebookDocument,
    NotebookDocumentMetadata,
    NotebookRemoveBlockAction,
    NotebookRemoveBlockActionPayload,
    NotebookUpdateMetadataAction,
    NotebookUpdateMetadataActionPayload,
    NotebookUpsertBlockAction,
    NotebookUpsertBlockActionPayload,
    QueryResponse,
    RadarCoordinateType,
    SqlBlock,
    TriggerActorModel,
)

from ..charts import ChartService

_UNSET = object()
type ChartFieldValue = str | list[str]
type ChartFieldInputs = dict[str, str] | dict[str, ChartFieldValue]


class NotebookEditor:
    """
    Editor class for creating and manipulating NotebookDocument instances.

    Provides methods for:
    - Creating new notebooks
    - Managing metadata
    - Manipulating blocks with typed data
    - Executing SQL blocks and managing data tables
    - Configuring chart blocks with typed chart configurations
    """

    def __init__(
        self,
        notebook: NotebookDocument | None = None,
        file_service: IFileServiceProtocol | None = None,
        query_session_service: IQuerySessionServiceProtocol | None = None,
        logger: logging.Logger | None = None,
        project_id: str | None = None,
    ):
        """
        Initialize the manager with an existing notebook or create a new one.

        Args:
            notebook: Existing NotebookDocument to manage, or None to create new
            file_service: FileService instance for API operations
            query_session_service: QuerySessionService instance for SQL execution
            logger: Custom logger instance, defaults to module logger if None
            project_id: Optional project ID for data-table fetching and validation
        """
        # Set up logger - use provided logger or fallback to module logger
        self.logger = logger or logging.getLogger(__name__)
        if notebook:
            self.notebook = notebook
        else:
            self.notebook = self._create_new_notebook()

        self.file_service = file_service
        self.query_session_service = query_session_service
        self.project_id = project_id
        self._data_table_cache: dict[str, InlineData] = {}

        # Action tracking for granular streaming
        # Use high-precision monotonically increasing sequence (microseconds)
        self._action_sequencer = MonotonicActionSequencer()
        self._pending_actions: list[ArtifactAction] = []

    @staticmethod
    def _create_new_notebook(title: str = "Untitled Notebook") -> NotebookDocument:
        """Create a new empty notebook document."""
        now = int(time.time() * 1000)  # Unix timestamp in milliseconds
        return NotebookDocument(title=title, created=now, modified=now, blocks=[])

    def create_notebook(self, title: str = "Untitled Notebook") -> NotebookDocument:
        """Create and return a new notebook document."""
        self.notebook = self._create_new_notebook(title)
        return self.notebook

    def load_notebook(self, notebook: NotebookDocument) -> None:
        """Load an existing notebook document for management."""
        self.notebook = notebook
        # Clear any pending actions from previous operations to ensure clean state
        self._pending_actions = []

    def get_notebook(self) -> NotebookDocument:
        """Get the current notebook document."""
        return self.notebook

    def take_actions(self) -> list[ArtifactAction]:
        """Return and clear pending actions for streaming."""
        actions = self._pending_actions
        self._pending_actions = []
        return actions

    def _next_action_sequence(self) -> int:
        """Get the next sequence number and increment."""
        return self._action_sequencer.next()

    @staticmethod
    def _block_type_value(block_type: Any) -> str:
        """Normalize block type values for streaming payloads."""
        return block_type.value if hasattr(block_type, "value") else str(block_type)

    # Metadata management
    def update_metadata(self, **kwargs) -> None:
        """Update metadata attributes. Pass keyword arguments for fields to update."""
        if self.notebook.metadata is None:
            self.notebook.metadata = NotebookDocumentMetadata()
        for key, value in kwargs.items():
            if hasattr(self.notebook.metadata, key):
                setattr(self.notebook.metadata, key, value)

                # Record action for each updated field
                self._pending_actions.append(
                    ArtifactAction(
                        root=NotebookUpdateMetadataAction(
                            sequence=self._next_action_sequence(),
                            action_type="updateMetadata",
                            payload=NotebookUpdateMetadataActionPayload(var_field=key, value=value),
                        )
                    )
                )
        self._update_modified()

    def get_metadata(self) -> NotebookDocumentMetadata | None:
        """Get the current metadata."""
        return self.notebook.metadata

    # Block management
    def _commit_blocks_with_aliases(self, candidate_blocks: list[NotebookBlock]) -> None:
        """Validate alias bindings on a prospective blocks list before committing.

        ``normalize_sql_aliases`` both binds missing ``df_N`` aliases and
        rejects invalid/duplicate names. It mutates block-data objects in
        place (the same objects this editor exposes), so validating on a
        shallow candidate copy keeps the live document untouched until
        validation passes — a failed edit must not wedge the in-memory
        notebook with an alias violation no action was recorded for.
        """
        candidate = self.notebook.model_copy(deep=False)
        candidate.blocks = candidate_blocks
        normalize_sql_aliases(candidate)
        self.notebook.blocks = candidate_blocks

    def add_block(self, block: NotebookBlock, position: int | None = None) -> None:
        """Add a new block to the notebook at the specified position."""
        # Normalize: ensure block is always wrapped in NotebookBlock
        if not hasattr(block, "root"):
            block = NotebookBlock(cast(Any, block))

        candidate_blocks = list(self.notebook.blocks)
        if position is None:
            candidate_blocks.append(block)
        else:
            candidate_blocks.insert(position, block)
        # Bind data aliases (df_N) for any result-bearing SQL blocks before
        # the action payload is serialized, so the upsert carries the alias.
        self._commit_blocks_with_aliases(candidate_blocks)

        # Get the actual index where it was placed (handles out-of-bounds position)
        try:
            actual_position = self.notebook.blocks.index(block)
        except ValueError:
            # Fallback for safety, though index() should find it
            actual_position = position if position is not None else len(self.notebook.blocks) - 1

        # Record action - block is guaranteed to be wrapped now
        b = cast(Any, block.root)
        self.logger.debug(
            f"NotebookEditor: Added block {b.id} of type {b.type} "
            f"at index {actual_position}. Total blocks: {len(self.notebook.blocks)}"
        )

        # All block data types are Pydantic models
        # Exclude None to avoid validation errors on frontend
        payload_data = b.data.model_dump(by_alias=True, exclude_none=True)

        # Use Pydantic model directly for type safety
        self._pending_actions.append(
            ArtifactAction(
                root=NotebookUpsertBlockAction(
                    sequence=self._next_action_sequence(),
                    action_type="upsertBlock",
                    payload=NotebookUpsertBlockActionPayload(
                        cid=str(b.id),
                        block_type=self._block_type_value(b.type),
                        data=payload_data,
                        position=actual_position,
                    ),
                )
            )
        )
        self._update_modified()

    def add_blocks(self, blocks: list[NotebookBlock], position: int | None = None) -> None:
        """Add multiple blocks to the notebook at the specified position."""
        # Normalize: ensure all blocks are wrapped
        wrapped_blocks = [
            block if hasattr(block, "root") else NotebookBlock(cast(Any, block)) for block in blocks
        ]

        if position is None:
            candidate_blocks = [*self.notebook.blocks, *wrapped_blocks]
        else:
            candidate_blocks = list(self.notebook.blocks)
            candidate_blocks[position:position] = wrapped_blocks
        # Bind data aliases (df_N) for any result-bearing SQL blocks before
        # the action payloads are serialized.
        self._commit_blocks_with_aliases(candidate_blocks)

        # Record actions for each block - all guaranteed to be wrapped now
        for block in wrapped_blocks:
            b = cast(Any, block.root)
            try:
                actual_idx = self.notebook.blocks.index(block)
            except ValueError:
                actual_idx = position if position is not None else 0

            # All block data types are Pydantic models
            payload_data = b.data.model_dump(by_alias=True, exclude_none=True)

            self.logger.debug(
                f"NotebookEditor: Added bulk block {b.id} of type {b.type} "
                f"at index {actual_idx}. Total blocks: {len(self.notebook.blocks)}"
            )

            # Use Pydantic model directly for type safety
            self._pending_actions.append(
                ArtifactAction(
                    root=NotebookUpsertBlockAction(
                        sequence=self._next_action_sequence(),
                        action_type="upsertBlock",
                        payload=NotebookUpsertBlockActionPayload(
                            cid=str(b.id),
                            block_type=self._block_type_value(b.type),
                            data=payload_data,
                            position=actual_idx,
                        ),
                    )
                )
            )
        self._update_modified()

    def edit_block(self, block_id: str, block_data: BlockData) -> None:
        """Edit an existing block by ID with the provided block data.

        Args:
            block_id: The ID of the block to edit
            block_data: Block data that should be one of the BlockData union types
        """
        for i, block in enumerate(self.notebook.blocks):
            # All blocks in self.notebook.blocks are guaranteed to be wrapped
            block_to_check = cast(Any, block.root)
            if block_to_check and str(block_to_check.id) == block_id:
                # Create a new block with the same type but updated data
                new_block = block_to_check.model_copy()
                # extract the root data from BlockData wrapper
                actual_data = block_data.root if hasattr(block_data, "root") else block_data
                # Safely assign data - we cast to bypass strict typing since we know
                # the data type matches the block type at runtime
                new_block = cast(Any, new_block)
                new_block.data = actual_data

                # Re-wrap in NotebookBlock (original is always wrapped). The
                # splice is validated (aliases) before it is committed, so a
                # duplicate alias leaves the notebook documents untouched.
                new_block_list = list(self.notebook.blocks)
                new_block_list[i] = NotebookBlock(new_block)
                self._commit_blocks_with_aliases(new_block_list)

                # Record action
                self._pending_actions.append(
                    ArtifactAction(
                        root=NotebookUpsertBlockAction(
                            sequence=self._next_action_sequence(),
                            action_type="upsertBlock",
                            payload=NotebookUpsertBlockActionPayload(
                                cid=block_id,
                                block_type=self._block_type_value(new_block.type),
                                data=cast(Any, actual_data).model_dump(
                                    by_alias=True, exclude_none=True
                                ),
                                position=i,
                            ),
                        )
                    )
                )

                self._update_modified()
                return
        raise ValueError(f"Block with ID {block_id} not found")

    def delete_block(self, block_id: str) -> None:
        """Delete a block by ID."""
        orig_len = len(self.notebook.blocks)
        self.notebook.blocks = [b for b in self.notebook.blocks if str(b.root.id) != block_id]

        if len(self.notebook.blocks) < orig_len:
            # Record action
            self._pending_actions.append(
                ArtifactAction(
                    root=NotebookRemoveBlockAction(
                        sequence=self._next_action_sequence(),
                        action_type="removeBlock",
                        payload=NotebookRemoveBlockActionPayload(cid=block_id),
                    )
                )
            )
            self._update_modified()

    def get_block(self, block_id: str) -> NotebookBlock | None:
        """Get a block by ID."""
        for block in self.notebook.blocks:
            # All blocks are guaranteed to be wrapped
            block_to_check = block.root
            if str(block_to_check.id) == block_id:
                return block
        return None

    def list_blocks(self) -> list[NotebookBlock]:
        """List all blocks in the notebook."""
        return self.notebook.blocks

    # Data table management (SQL execution)
    async def execute_sql_block(
        self,
        block_id: str,
        project_id: str,
        session_id: str | None = None,
        triggered_by: TriggerActorModel | None = None,
    ) -> QueryResponse:
        """
        Execute the SQL in a SQL block using QuerySessionService and update
        the data tables.

        Args:
            block_id: ID of the SQL block
            project_id: Project ID for the query session
            session_id: Optional session ID to reuse
            triggered_by: Optional trigger source (e.g., "Agent", "UI:{userId}")

        Returns:
            QueryResponse with execution results containing:
            - results: List of Result objects with columns, rows, metadata
            - totalExecutionTimeMs: Total execution time
            - success: Whether execution was successful
            - errorMessage: Error message if execution failed
        """
        self.logger.info(
            f"Starting SQL block execution: block_id={block_id}, "
            f"project_id={project_id}, session_id={session_id}"
        )

        if not self.query_session_service:
            self.logger.error("QuerySessionService not provided - cannot execute SQL block")
            raise ValueError("QuerySessionService not provided. Cannot execute SQL block.")

        block = self.get_block(block_id)
        if not block:
            self.logger.error(f"Block not found: block_id={block_id}")
            raise ValueError(f"Block {block_id} not found")

        # Block from get_block is always wrapped
        block_to_check = cast(Any, block.root)
        if not isinstance(block_to_check, SqlBlock):
            self.logger.error(
                f"Block is not a SQL block: block_id={block_id}, block_type={type(block_to_check)}"
            )
            raise ValueError(f"Block {block_id} is not a SQL block")

        self.logger.info(
            f"Validated SQL block: block_id={block_id}, sql_length={len(block_to_check.data.code)}"
        )

        try:
            # Execute query using QuerySessionService
            self.logger.info(f"Executing SQL query for block: {block_id}")
            query_response = await self.query_session_service.execute_sql_with_session_management(
                project_id=project_id,
                sql_query=block_to_check.data.code,
                session_id=session_id,
                triggered_by=triggered_by,
                store_result_as_resource=True,  # Store as resource for notebooks
            )

            self.logger.info(
                f"SQL execution completed: success={query_response.success}, "
                f"execution_time={query_response.total_execution_time_ms}ms"
            )

            # Only link the data table if execution was successful
            if query_response.success:
                ds_id_from_response = (
                    str(query_response.data_id) if query_response.data_id else None
                )

                # Results are always stored as resources now
                if ds_id_from_response:
                    self.logger.info(
                        "Query returned a data_table_id; linking block to "
                        "resource-backed data table: "
                        f"{ds_id_from_response}"
                    )

                    # Simply link the block to the resource ID
                    # No need to load or store data-table content in notebook
                    self._link_block_to_data_table(block_id, ds_id_from_response)

                    self._update_modified()
                else:
                    self.logger.warning(
                        "SQL execution succeeded but no data_table_id returned. "
                        "This may indicate an empty result set."
                    )

                self.logger.info(f"SQL block execution completed successfully: block_id={block_id}")

            else:
                self.logger.warning(
                    f"SQL execution failed: block_id={block_id}, "
                    f"error={query_response.error_message}"
                )

            # Return the QueryResponse directly
            return query_response
        except Exception as e:
            # Return error QueryResponse for consistent error handling
            self.logger.error(
                f"SQL block execution failed: block_id={block_id}, error={e!s}",
                exc_info=True,
            )
            return QueryResponse(
                result=None,
                total_execution_time_ms=0,
                success=False,
                error_message=f"SQL execution failed: {e!s}",
                data_id=None,
            )

    def _link_block_to_data_table(self, block_id: str, data_table_id: str) -> None:
        """
        Link a block to a data table by updating the block's data reference.

        Args:
            block_id: ID of the block to link
            data_table_id: ID of the data table to link to
        """
        block = self.get_block(block_id)
        if block:
            # Block from get_block is always wrapped
            block_to_check = block.root
            if isinstance(block_to_check, SqlBlock):
                block_to_check.data.data_ref = DataRef(data_id=data_table_id)
                # Bind the df_N alias before the action payload is serialized
                # so client surfaces see the name the block just acquired.
                normalize_sql_aliases(self.notebook)
                # Record action
                self._pending_actions.append(
                    ArtifactAction(
                        root=NotebookUpsertBlockAction(
                            sequence=self._next_action_sequence(),
                            action_type="upsertBlock",
                            payload=NotebookUpsertBlockActionPayload(
                                cid=block_id,
                                block_type=self._block_type_value(block_to_check.type),
                                data=cast(Any, block_to_check.data).model_dump(by_alias=True),
                            ),
                        )
                    )
                )

    def validate_data_table_exists(self, data_table_id: str) -> bool:
        """
        Check if a data ID exists in any SQL block in the notebook.

        Args:
            data_table_id: The data ID to check

        Returns:
            True if the data ID exists, False otherwise
        """
        for block in self.notebook.blocks:
            # All blocks are guaranteed to be wrapped
            block_to_check = block.root
            if isinstance(block_to_check, SqlBlock) and (
                block_to_check.data.data_ref
                and block_to_check.data.data_ref.data_id == data_table_id
            ):
                return True
        return False

    async def fetch_data_table(self, data_table_id: str) -> InlineData | None:
        """
        Fetch data-table details and cache them.

        Args:
            data_table_id: The data ID to fetch

        Returns:
            InlineData object or None if not found or fetch fails
        """
        # Return from cache if available
        if data_table_id in self._data_table_cache:
            return self._data_table_cache[data_table_id]

        if not self.file_service or not self.project_id:
            self.logger.warning(
                f"FileService or project_id not provided. Cannot fetch data table {data_table_id}"
            )
            return None

        try:
            self.logger.debug(f"Fetching data table {data_table_id} from API")
            # Use the specialized method from FileService
            inline_data = await self.file_service.get_data_table_file(
                self.project_id, data_table_id
            )

            # Cache the result
            if inline_data:
                self._data_table_cache[data_table_id] = inline_data

            return inline_data
        except Exception as e:
            self.logger.error(f"Failed to fetch data table {data_table_id}: {e!s}")
            return None

    def register_data_table(self, inline_data: InlineData, data_table_id: str | None = None) -> str:
        """
        Register a data table in the editor's cache.
        This is useful for transient data tables not yet persisted to backend.

        Args:
            inline_data: The InlineData object to register
            data_table_id: Optional ID to use for the data table.
                           If not provided, a new UUID will be generated.

        Returns:
            The ID of the registered data table
        """
        ds_id = data_table_id or str(uuid4())
        self._data_table_cache[ds_id] = inline_data
        return ds_id

    async def get_data_table_columns(self, data_table_id: str) -> list[str]:
        """
        Get the available column names from a data table.

        Args:
            data_table_id: The data table ID to query

        Returns:
            List of column names available in the data table

        Raises:
            ValueError: If the data table is not found or has no column information
        """
        # First check if the data table is in the notebook
        if not self.validate_data_table_exists(data_table_id):
            raise ValueError(f"Data table {data_table_id} not found in notebook")

        # Fetch or refresh data-table details
        data_source = await self.fetch_data_table(data_table_id)

        if not data_source or not data_source.table:
            raise ValueError(
                f"Data table {data_table_id} has no result set or table content. "
                "Ensure the previous SQL block has been executed successfully."
            )

        table = data_source.table
        if not table.columns:
            raise ValueError(f"Table in data table {data_table_id} has no column definitions.")

        return [col.name for col in table.columns]

    async def validate_chart_fields(
        self, data_table_id: str, required_fields: ChartFieldInputs
    ) -> list[str]:
        """
        Validate that all required fields exist in a data table.

        Args:
            data_table_id: The data table ID to validate against
            required_fields: Dictionary of field names to validate.
                             Keys are field parameter names (e.g., 'x_field', 'y_field')
                             Values are either string field names or string lists for
                             tuple-like chart inputs such as stock OHLC fields.

        Returns:
            List of validation error messages (empty if all valid)

        Raises:
            ValueError: If the data table is not found
        """
        errors = []

        # First check if the data table exists in the notebook
        if not self.validate_data_table_exists(data_table_id):
            raise ValueError(f"Data table {data_table_id} not found in notebook")

        # Get available columns - will raise ValueError if none found/accessible
        available_columns = await self.get_data_table_columns(data_table_id)

        # Create a mapping for case-insensitive lookup
        col_lookup = {col.lower(): col for col in available_columns}

        normalized_fields = cast(dict[str, ChartFieldValue], required_fields)

        for param_name, field_value in normalized_fields.items():
            if isinstance(field_value, list):
                normalized_values: list[str] = []
                for index, item in enumerate(field_value):
                    if not item or item.strip() == "":
                        errors.append(f"{param_name}[{index}] cannot be empty")
                    elif item.lower() not in col_lookup:
                        errors.append(
                            f"Column '{item}' (for {param_name}[{index}]) "
                            "not found in data table. "
                            f"Available columns: {', '.join(available_columns)}"
                        )
                    else:
                        normalized_values.append(col_lookup[item.lower()])

                if len(normalized_values) == len(field_value):
                    normalized_fields[param_name] = normalized_values
                continue

            if not field_value or field_value.strip() == "":
                errors.append(f"{param_name} cannot be empty")
            elif field_value.lower() not in col_lookup:
                errors.append(
                    f"Column '{field_value}' (for {param_name}) "
                    "not found in data table. "
                    f"Available columns: {', '.join(available_columns)}"
                )
            else:
                # Normalize to the actual column name found in the data table
                normalized_fields[param_name] = col_lookup[field_value.lower()]

        return errors

    # Chart block management
    def add_chart_block(
        self,
        chart_config: ChartConfig,
        data_ref: DataRef | None = None,
        inline_data: InlineData | None = None,
        position: int | None = None,
    ) -> NotebookBlock:
        """
        Add a new chart block with the specified chart configuration.

        Args:
            chart_config: Complete chart configuration object
            data_ref: Data-table reference for the chart
            inline_data: Embedded data table (InlineData) for the chart
            position: Position to insert the block
        """
        # Create chart block data with config and dataRef as separate fields.
        # If inline_data is provided, it will be included in the block data.
        chart_block_data = ChartSpec(
            config=chart_config, data_ref=data_ref, inline_data=inline_data
        )
        chart_block = ChartBlock(id=str(uuid4()), type="chart", data=chart_block_data)
        # Wrap in NotebookBlock RootModel
        notebook_block = NotebookBlock(chart_block)
        self.add_block(notebook_block, position)
        # Return the created block so callers can access its ID
        return notebook_block

    def add_code_block(
        self,
        code: str,
        language: Literal["python"] = "python",
        position: int | None = None,
        title: str | None = None,
    ) -> NotebookBlock:
        """
        Add a new code block with the specified code and language.

        Args:
            code: Code content
            language: Programming language for syntax highlighting
            position: Position to insert the block
            title: Optional title for the code block
        """
        code_block_data = CodeBlockData(code=code, language=language, title=title)
        code_block = CodeBlock(id=str(uuid4()), type="code", data=code_block_data)
        # Wrap in NotebookBlock RootModel
        notebook_block = NotebookBlock(code_block)
        self.add_block(notebook_block, position)
        # Return the created block so callers can access its ID
        return notebook_block

    def edit_chart_block(
        self, block_id: str, chart_config: ChartConfig, data_ref: DataRef | None = None
    ) -> None:
        """
        Edit an existing chart block with new chart configuration.

        Args:
            block_id: ID of the chart block to edit
            chart_config: New chart configuration object
            data_ref: New data-table reference (optional)
        """
        # Create chart block data with config and dataRef as separate fields
        chart_block_data = ChartSpec(config=chart_config, data_ref=data_ref)
        # Wrap in BlockData for type safety
        self.edit_block(block_id, BlockData(chart_block_data))

    def edit_code_block(
        self,
        block_id: str,
        code: str,
        language: Literal["python"] = "python",
        title: str | None = None,
    ) -> None:
        """
        Edit an existing code block with new code and language.

        Args:
            block_id: ID of the code block to edit
            code: New code content
            language: New programming language
            title: Optional new title for the code block
        """
        code_block_data = CodeBlockData(code=code, language=language, title=title)
        # Wrap in BlockData for type safety
        self.edit_block(block_id, BlockData(code_block_data))

    def update_code_block_execution(
        self,
        block_id: str,
        *,
        outputs: list[CodeExecutionOutput] | object | None = _UNSET,
        is_executing: bool | object | None = _UNSET,
        last_executed: int | object | None = _UNSET,
    ) -> NotebookBlock:
        """Update execution metadata for an existing code block without changing its code."""
        block = self.get_block(block_id)
        if block is None:
            raise ValueError(f"Block {block_id} not found")

        block_to_check = cast(Any, block.root)
        if not isinstance(block_to_check, CodeBlock):
            raise ValueError(f"Block {block_id} is not a code block")

        code_block_data = block_to_check.data.model_copy(deep=True)
        if outputs is not _UNSET:
            code_block_data.outputs = cast(list[CodeExecutionOutput] | None, outputs)
        if is_executing is not _UNSET:
            code_block_data.is_executing = cast(bool | None, is_executing)
        if last_executed is not _UNSET:
            code_block_data.last_executed = cast(int | None, last_executed)

        self.edit_block(block_id, BlockData(code_block_data))
        updated_block = self.get_block(block_id)
        if updated_block is None:
            raise ValueError(f"Failed to update code block {block_id}")
        return updated_block

    # Convenience methods for creating chart configurations
    @staticmethod
    def create_line_chart(
        title: str,
        x_field: str,
        y_field: str,
        height: float = 400.0,
        color_field: str | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create a line chart configuration (delegates to ChartService)."""
        return ChartService.create_line_chart_config(
            title=title,
            x_field=x_field,
            y_field=y_field,
            height=height,
            color_field=color_field,
            **kwargs,
        )

    @staticmethod
    def create_bar_chart(
        title: str,
        x_field: str,
        y_field: str,
        height: float = 400.0,
        color_field: str | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create a bar chart configuration (delegates to ChartService)."""
        return ChartService.create_bar_chart_config(
            title=title,
            x_field=x_field,
            y_field=y_field,
            height=height,
            color_field=color_field,
            **kwargs,
        )

    @staticmethod
    def create_pie_chart(
        title: str, angle_field: str, color_field: str, height: float = 400.0, **kwargs
    ) -> ChartConfig:
        """Create a pie chart configuration (delegates to ChartService)."""
        return ChartService.create_pie_chart_config(
            title=title,
            angle_field=angle_field,
            color_field=color_field,
            height=height,
            **kwargs,
        )

    @staticmethod
    def create_scatter_chart(
        title: str,
        x_field: str,
        y_field: str,
        height: float = 400.0,
        color_field: str | None = None,
        size_field: str | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create a scatter chart configuration (delegates to ChartService)."""
        return ChartService.create_scatter_chart_config(
            title=title,
            x_field=x_field,
            y_field=y_field,
            height=height,
            color_field=color_field,
            size_field=size_field,
            **kwargs,
        )

    @staticmethod
    def create_area_chart(
        title: str,
        x_field: str,
        y_field: str,
        height: float = 400.0,
        color_field: str | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create an area chart configuration (delegates to ChartService)."""
        return ChartService.create_area_chart_config(
            title=title,
            x_field=x_field,
            y_field=y_field,
            height=height,
            color_field=color_field,
            **kwargs,
        )

    @staticmethod
    def create_column_chart(
        title: str,
        x_field: str,
        y_field: str,
        height: float = 400.0,
        color_field: str | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create a column chart configuration (delegates to ChartService)."""
        return ChartService.create_column_chart_config(
            title=title,
            x_field=x_field,
            y_field=y_field,
            height=height,
            color_field=color_field,
            **kwargs,
        )

    @staticmethod
    def create_dual_axes_chart(
        title: str,
        x_field: str,
        left_y_field: str,
        left_chart_type: DualAxesChartType,
        right_y_field: str,
        right_chart_type: DualAxesChartType,
        height: float = 400.0,
        left_color_field: str | None = None,
        right_color_field: str | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create a dual axes chart configuration (delegates to ChartService)."""
        return ChartService.create_dual_axes_chart_config(
            title=title,
            x_field=x_field,
            left_y_field=left_y_field,
            left_chart_type=left_chart_type,
            right_y_field=right_y_field,
            right_chart_type=right_chart_type,
            height=height,
            left_color_field=left_color_field,
            right_color_field=right_color_field,
            **kwargs,
        )

    @staticmethod
    def create_funnel_chart(
        title: str,
        x_field: str,
        y_field: str,
        height: float = 400.0,
        compare_field: str | None = None,
        series_field: str | None = None,
        is_transposed: bool | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create a funnel chart configuration (delegates to ChartService)."""
        return ChartService.create_funnel_chart_config(
            title=title,
            x_field=x_field,
            y_field=y_field,
            height=height,
            compare_field=compare_field,
            series_field=series_field,
            is_transposed=is_transposed,
            **kwargs,
        )

    @staticmethod
    def create_heatmap_chart(
        title: str,
        x_field: str,
        y_field: str,
        height: float = 400.0,
        color_field: str | None = None,
        size_field: str | None = None,
        shape_field: str | None = None,
        mark: MarkTypes | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create a heatmap chart configuration (delegates to ChartService)."""
        return ChartService.create_heatmap_chart_config(
            title=title,
            x_field=x_field,
            y_field=y_field,
            height=height,
            color_field=color_field,
            size_field=size_field,
            shape_field=shape_field,
            mark=mark,
            **kwargs,
        )

    @staticmethod
    def create_histogram_chart(
        title: str,
        bin_field: str,
        height: float = 400.0,
        color_field: str | None = None,
        bin_width: float | None = None,
        bin_number: int | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create a histogram chart configuration (delegates to ChartService)."""
        return ChartService.create_histogram_chart_config(
            title=title,
            bin_field=bin_field,
            height=height,
            color_field=color_field,
            bin_width=bin_width,
            bin_number=bin_number,
            **kwargs,
        )

    @staticmethod
    def create_box_chart(
        title: str,
        x_field: str,
        y_field: str,
        height: float = 400.0,
        color_field: str | None = None,
        box_type: BoxChartType | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create a box chart configuration (delegates to ChartService)."""
        return ChartService.create_box_chart_config(
            title=title,
            x_field=x_field,
            y_field=y_field,
            height=height,
            color_field=color_field,
            box_type=box_type,
            **kwargs,
        )

    @staticmethod
    def create_radar_chart(
        title: str,
        x_field: str,
        y_field: str,
        height: float = 400.0,
        color_field: str | None = None,
        coordinate_type: RadarCoordinateType | None = None,
        **kwargs,
    ) -> ChartConfig:
        """Create a radar chart configuration (delegates to ChartService)."""
        return ChartService.create_radar_chart_config(
            title=title,
            x_field=x_field,
            y_field=y_field,
            height=height,
            color_field=color_field,
            coordinate_type=coordinate_type,
            **kwargs,
        )

    @staticmethod
    def create_stock_chart(
        title: str,
        x_field: str,
        open_field: str,
        close_field: str,
        low_field: str,
        high_field: str,
        height: float = 400.0,
        **kwargs,
    ) -> ChartConfig:
        """Create a stock chart configuration (delegates to ChartService)."""
        return ChartService.create_stock_chart_config(
            title=title,
            x_field=x_field,
            open_field=open_field,
            close_field=close_field,
            low_field=low_field,
            high_field=high_field,
            height=height,
            **kwargs,
        )

    def _update_modified(self) -> None:
        """Update the modified timestamp."""
        self.notebook.modified = int(time.time() * 1000)

    # File service integration
    async def create_notebook_file(
        self, project_id: str, name: str | None = None
    ) -> FileUploadResponse:
        """
        Create the current notebook as a file in the platform.

        Args:
            project_id: The project ID to create the notebook in
            name: Optional name for the file (defaults to notebook title)

        Returns:
            FileUploadResponse containing the created file

        Raises:
            ValueError: If file_service is not provided or notebook validation fails
        """
        if not self.file_service:
            raise ValueError("FileService not provided. Cannot create notebook file.")

        # Validate notebook before saving
        validation_errors = self.validate_notebook()
        if validation_errors:
            raise ValueError(f"Notebook validation failed. Errors: {', '.join(validation_errors)}")

        file_name = name or self.notebook.title
        return await self.file_service.create_notebook(
            project_id=project_id, notebook=self.notebook, name=file_name
        )

    async def update_notebook_file(
        self, project_id: str, file_id: str, name: str | None = None
    ) -> FileModel:
        """
        Update an existing notebook file with the current notebook content.

        Args:
            project_id: The project ID for authorization
            file_id: The file ID to update
            name: Optional new name for the file

        Returns:
            FileModel of the updated file

        Raises:
            ValueError: If file_service is not provided or notebook validation fails
        """
        if not self.file_service:
            raise ValueError("FileService not provided. Cannot update notebook file.")

        # Validate notebook before saving
        validation_errors = self.validate_notebook()
        if validation_errors:
            raise ValueError(f"Notebook validation failed. Errors: {', '.join(validation_errors)}")

        return await self.file_service.update_notebook(
            project_id=project_id, file_id=file_id, notebook=self.notebook, name=name
        )

    # Validation
    def validate_notebook(self) -> list[str]:
        """Validate the notebook and return any errors."""
        try:
            # Re-validate the current notebook instance
            NotebookDocument.model_validate(self.notebook.model_dump(exclude_none=True))
            return []
        except Exception as e:
            return [str(e)]

    async def load_notebook_from_file(self, project_id: str, file_id: str) -> None:
        """
        Load a notebook document from a file using the FileService.

        Args:
            project_id: The project ID for authorization
            file_id: The ID of the file to load the notebook from

        Raises:
            ValueError: If file_service is not provided or loading fails
        """
        if not self.file_service:
            raise ValueError("FileService not provided. Cannot load notebook from file.")

        try:
            content = await self.file_service.get_file_content(project_id, file_id)
            notebook_data = json.loads(content)
            notebook = NotebookDocument.model_validate(notebook_data)
            self.load_notebook(notebook)
        except Exception as e:
            raise ValueError(f"Failed to load notebook from file {file_id}: {e!s}") from e

    # Persistence methods
    async def save_notebook(self, project_id: str, file_id: str, name: str | None = None) -> None:
        """
        Save the current notebook to the specified file.

        Args:
            project_id: The project ID for authorization
            file_id: The file ID to save to
            name: Optional new name for the file

        Raises:
            ValueError: If file_service is not provided
        """
        if not self.file_service:
            raise ValueError("FileService not provided. Cannot save notebook.")

        # Validate notebook before saving
        validation_errors = self.validate_notebook()
        if validation_errors:
            raise ValueError(f"Notebook validation failed. Errors: {', '.join(validation_errors)}")

        await self.file_service.update_notebook(
            project_id=project_id, file_id=file_id, notebook=self.notebook, name=name
        )

    async def save_if_modified(
        self, project_id: str, file_id: str, name: str | None = None
    ) -> bool:
        """
        Save the notebook only if it has been modified since last save.

        Args:
            project_id: The project ID for authorization
            file_id: The file ID to save to
            name: Optional new name for the file

        Returns:
            True if saved, False if not modified

        Raises:
            ValueError: If file_service is not provided
        """
        # For now, always save since we don't track modification state
        # In the future, we could add a dirty flag
        await self.save_notebook(project_id, file_id, name)
        return True
