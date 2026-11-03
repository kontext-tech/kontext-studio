"""Notebook tools for managing notebooks and blocks in Kontext."""

import asyncio
import json
import os
from typing import Any
from uuid import uuid4

from kontext.agent import RuntimeToolContext
from kontext.agent.tools import (
    creates_artifact,
    deletes_artifact,
    reads_artifact,
    tool_meta,
    updates_artifact,
)
from kontext.agentic.utils.guid_validation import validate_guid, validate_guids
from kontext.common.protocols import AIToolkitServiceProviderProtocol
from kontext.common.python_execution.policy import validate_python_code
from kontext.file.notebook.editor import NotebookEditor
from kontext.schema import (
    ArtifactType,
    BlockData,
    ChartSpec,
    CodeBlockData,
    DelimiterBlockData,
    HeaderBlock,
    HeaderBlockData,
    ImageBlockData,
    ImagePickerBlockData,
    ListBlock,
    ListBlockData,
    ListBlockMeta,
    ListItem,
    ListItemMeta,
    ListStyle,
    MermaidBlock,
    MermaidBlockData,
    NotebookBatchResult,
    NotebookBlock,
    NotebookBlockBatchResult,
    NotebookBlockListResult,
    NotebookBlockResult,
    NotebookBlockType,
    NotebookDocumentMetadata,
    NotebookListResult,
    NotebookMultiBlockResult,
    NotebookMutationResult,
    NotebookResult,
    ParagraphBlock,
    ParagraphBlockData,
    ProjectModel,
    QuoteAlignment,
    QuoteBlock,
    QuoteBlockData,
    SqlBlockData,
    TableBlock,
    TableBlockData,
)

from .kontext_toolkit import KontextToolkit, ToolkitScope
from .markdown_parser import markdown_to_html, parse_markdown, validate_header_level
from .notebook._charts import NotebookChartsMixin
from .notebook._core import NotebookCoreMixin
from .notebook._python_blocks import NotebookPythonBlocksMixin

# Block type -> data model. `edit_block` is intentionally generic at the tool
# boundary; validating against the existing block's type keeps an ambiguous
# payload (for example, a code object for an SQL block) from corrupting it.
BlockDataModel = (
    ParagraphBlockData
    | HeaderBlockData
    | ListBlockData
    | CodeBlockData
    | QuoteBlockData
    | TableBlockData
    | DelimiterBlockData
    | ImageBlockData
    | ImagePickerBlockData
    | SqlBlockData
    | MermaidBlockData
    | ChartSpec
)

_BLOCK_DATA_MODELS: dict[NotebookBlockType, type[BlockDataModel]] = {
    NotebookBlockType.PARAGRAPH: ParagraphBlockData,
    NotebookBlockType.HEADER: HeaderBlockData,
    NotebookBlockType.LIST: ListBlockData,
    NotebookBlockType.CODE: CodeBlockData,
    NotebookBlockType.QUOTE: QuoteBlockData,
    NotebookBlockType.TABLE: TableBlockData,
    NotebookBlockType.DELIMITER: DelimiterBlockData,
    NotebookBlockType.IMAGE: ImageBlockData,
    NotebookBlockType.IMAGEPICKER: ImagePickerBlockData,
    NotebookBlockType.SQL: SqlBlockData,
    NotebookBlockType.MERMAID: MermaidBlockData,
    NotebookBlockType.CHART: ChartSpec,
}


class NotebookTools(
    NotebookChartsMixin,
    NotebookPythonBlocksMixin,
    NotebookCoreMixin,
    KontextToolkit,
):
    """Toolkit for notebook and block management operations."""

    def __init__(
        self,
        project: ProjectModel | None = None,
        runtime_provider: AIToolkitServiceProviderProtocol | None = None,
        session_id: str | None = None,
        chat_session_id: str | None = None,
        allow_python_blocks: bool = False,
        allow_python_execution_persistence: bool = False,
        allow_charts: bool = True,
        catalog_connection_id: str | None = None,
        default_namespace: str | None = None,
        default_entity_id: str | None = None,
        engine_type: str | None = None,
        scope: ToolkitScope | None = None,
        editor_lock: asyncio.Lock | None = None,
    ) -> None:
        """Initialize notebook toolkit.

        Args:
            project: Project model with full context
            session_id: Optional session ID to reuse
            chat_session_id: Optional chat session ID for linking query sessions
            allow_python_blocks: Whether to allow python block mutation tools
            allow_python_execution_persistence: Whether to allow notebook-side persistence of Python execution state
            allow_charts: Whether to allow chart-creation tools (`import_chart` and the `add_*_chart` tools)
            engine_type: Optional default engine type
            editor_lock: Optional lock shared with the notebook Python execution
                toolkit so block mutation and execution cannot race.
        """
        # Collect all tool methods (those decorated with @reads_artifact, @creates_artifact, etc.)
        tools = [
            self.get_notebook,
            self.get_notebooks,
            self.create_notebook,
            self.update_notebook,
            self.list_notebooks,
            self.duplicate_notebook,
            self.add_data_table,
            self.add_paragraph,
            self.add_mermaid_diagram,
            self.add_list,
            self.edit_list_block,
            self.add_quote,
            self.add_table,
            self.add_header,
            self.add_summary,
            self.edit_block,
            self.delete_block,
            self.delete_blocks,
            self.list_blocks,
            self.get_notebook_outline,
            self.get_block,
            self.get_blocks,
        ]

        if allow_python_blocks:
            tools.extend([self.add_python, self.edit_python_code])

        if allow_python_execution_persistence:
            tools.extend(
                [
                    self.import_executed_python,
                    self.persist_python_execution_state,
                ]
            )

        if allow_charts:
            tools.extend(
                [
                    self.import_chart,
                    self.edit_chart_block,
                    self.add_line_chart,
                    self.add_bar_chart,
                    self.add_pie_chart,
                    self.add_scatter_chart,
                    self.add_area_chart,
                    self.add_column_chart,
                    self.add_dual_axes_chart,
                    self.add_funnel_chart,
                    self.add_heatmap_chart,
                    self.add_histogram_chart,
                    self.add_box_chart,
                    self.add_radar_chart,
                    self.add_stock_chart,
                ]
            )

        super().__init__(
            name="NotebookTools",
            project=project,
            runtime_provider=runtime_provider,
            session_id=session_id,
            chat_session_id=chat_session_id,
            catalog_connection_id=catalog_connection_id,
            default_namespace=default_namespace,
            default_entity_id=default_entity_id,
            engine_type=engine_type,
            scope=scope,
            tools=tools,
        )
        self.file_service = self.get_file_service()
        self.query_session_service = self.get_query_session_service()
        self.allow_python_blocks = allow_python_blocks
        self.allow_python_execution_persistence = allow_python_execution_persistence

        # Validate project_id
        validate_guid(self.project_id, "project_id")

        self.editor = NotebookEditor(
            file_service=self.file_service,
            query_session_service=self.query_session_service,
            logger=self.logger,  # Pass the logger to NotebookEditor
            project_id=self.project_id,
        )

        # Agno runs every tool call emitted in a single assistant turn
        # concurrently (models.base.arun_function_calls gathers them), and
        # these tools mutate whole-document notebook state through one shared
        # editor with load -> mutate -> save cycles. Concurrent calls
        # therefore race and lose updates (observed in the wild: parallel
        # add_header + add_paragraph + add_data_table left only the header on
        # disk and the next chart add failed its state check). Serialize all
        # editor access through this lock, and share it with the notebook
        # Python execution toolkit so execution cannot race a block edit.
        self._editor_lock = editor_lock or asyncio.Lock()

    @reads_artifact(NotebookResult, artifact_type=ArtifactType.NOTEBOOK)
    @validate_guids("notebook_id")
    async def get_notebook(self, notebook_id: str) -> str:
        """Retrieve notebook by ID.

        :param notebook_id: Notebook ID.
        """
        try:
            self.logger.info(f"Retrieving notebook: {notebook_id}")

            # Load the notebook from the resource using the pre-instantiated editor
            async with self._editor_lock:
                await self.editor.load_notebook_from_file(self.project_id, notebook_id)
                notebook = self.editor.get_notebook()

            result = NotebookResult(
                success=True,
                notebook_id=notebook_id,
                notebook=notebook,
                message=f"Successfully retrieved notebook '{notebook.title}'",
            )

            self.logger.info(f"Successfully retrieved notebook: {notebook.title}")
            return self._wrap_result(result)

        except Exception as e:
            error_msg = f"Failed to retrieve notebook {notebook_id}: {e!s}"
            self.logger.error(error_msg, exc_info=True)

            error_result = NotebookResult(
                success=False,
                notebook_id=notebook_id,
                notebook=None,
                message=f"Error retrieving notebook {notebook_id}: {e!s}",
            )
            return self._wrap_result(error_result)

    @tool_meta(NotebookBatchResult, display_name="Get Notebooks (Batch)", emit_tool_call=True)
    async def get_notebooks(self, notebook_ids: list[str]) -> str:
        """Retrieve several notebooks in one call.

        :param notebook_ids: Notebook IDs.
        """
        notebooks = await self._collect_batch_items(
            notebook_ids,
            fetch=self.get_notebook,
            parse_into=NotebookResult,
            failure=lambda notebook_id, exc: NotebookResult(
                success=False, notebook_id=notebook_id, notebook=None, message=str(exc)
            ),
        )
        failed_count = self._failed_count(notebooks)
        return self._wrap_result(
            NotebookBatchResult(
                success=bool(notebooks) and failed_count == 0,
                message=f"Retrieved {len(notebooks)} notebook(s); {failed_count} failed.",
                notebooks=notebooks,
                notebooks_count=len(notebooks),
                failed_count=failed_count,
            )
        )

    @creates_artifact(
        NotebookMutationResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True
    )
    async def create_notebook(
        self,
        title: str = "Untitled Notebook",
        metadata: NotebookDocumentMetadata | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Create a new notebook.

        :param title: Notebook title.
        :param metadata: Optional metadata.
        :param run_context: runtime context.
        """
        try:
            # Try creating with the original title first
            self.logger.info(f"Creating notebook '{title}' in project: {self.project_id}")

            if not self.file_service:
                raise ValueError("File service is not available")

            # Create a new notebook using the editor
            editor = NotebookEditor(logger=self.logger)
            notebook = editor.create_notebook(title)

            # Update metadata if provided
            if metadata:
                editor.update_metadata(**metadata.model_dump(exclude_none=True))

            # Try to create the notebook as a resource with original title
            try:
                response = await self.file_service.create_notebook(
                    project_id=self.project_id, notebook=notebook, name=title
                )

                # Actions are now passed through the result
                actions = editor.take_actions()

                result = NotebookMutationResult(
                    success=True,
                    actions=actions,
                    notebook_id=response.file.id,
                    name=response.file.name,
                    message=f"Successfully created notebook '{title}'",
                )

                self.logger.info(f"Successfully created notebook: {response.file.id}")

                # Register artifact if we have a chat session
                await self.link_artifact_to_session(
                    artifact_id=response.file.id,
                    artifact_type=ArtifactType.NOTEBOOK,
                    title=response.file.name,
                    run_context=run_context,
                )

                return self._wrap_result(result)

            except Exception as naming_error:
                # If creation fails (likely due to naming conflict), retry with unique name
                self.logger.info(
                    f"Original title '{title}' failed, retrying with unique name. Error: {naming_error!s}"
                )

                unique_title = self._generate_unique_notebook_name(title)
                self.logger.info(f"Retrying notebook creation with unique title '{unique_title}'")

                # Update the notebook with the unique title
                notebook = editor.create_notebook(unique_title)

                # Update metadata if provided
                if metadata:
                    editor.update_metadata(**metadata.model_dump(exclude_none=True))

                # Create the notebook as a resource with unique title
                response = await self.file_service.create_notebook(
                    project_id=self.project_id, notebook=notebook, name=unique_title
                )

                # Actions are now passed through the result
                actions = editor.take_actions()

                result = NotebookMutationResult(
                    success=True,
                    actions=actions,
                    notebook_id=response.file.id,
                    name=response.file.name,
                    message=f"Successfully created notebook '{unique_title}' (original title '{title}' was unavailable)",
                )

                self.logger.info(
                    f"Successfully created notebook with unique title: {response.file.id}"
                )

                # Register artifact if we have a chat session
                await self.link_artifact_to_session(
                    artifact_id=response.file.id,
                    artifact_type=ArtifactType.NOTEBOOK,
                    title=response.file.name,
                    run_context=run_context,
                )

                return self._wrap_result(result)

        except Exception as e:
            error_msg = f"Failed to create notebook: {e!s}"
            self.logger.error(error_msg, exc_info=True)

            error_result = NotebookMutationResult(
                success=False, message=f"Error creating notebook: {error_msg}"
            )
            return self._wrap_result(error_result)

    @updates_artifact(
        NotebookMutationResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True
    )
    @validate_guids("notebook_id")
    async def update_notebook(
        self,
        notebook_id: str,
        title: str | None = None,
        metadata: NotebookDocumentMetadata | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Update notebook title/metadata.

        :param notebook_id: Notebook ID.
        :param title: Optional new title.
        :param metadata: Optional new metadata.
        :param run_context: runtime context.
        """
        try:
            self.logger.info(f"Updating notebook: {notebook_id}")

            # Load the current notebook
            async with self._editor_lock:
                await self.editor.load_notebook_from_file(self.project_id, notebook_id)
                current_notebook = self.editor.get_notebook()

                # Apply updates to title and/or metadata
                updated_title = title if title is not None else current_notebook.title
                updated_metadata = metadata if metadata is not None else current_notebook.metadata

                # Create updated notebook with only title/metadata changes
                updated_notebook = current_notebook.model_copy()
                updated_notebook.title = updated_title
                updated_notebook.metadata = updated_metadata

                # Update the editor's notebook and save
                self.editor.load_notebook(updated_notebook)
                await self.editor.save_notebook(
                    self.project_id, notebook_id, name=updated_title if title is not None else None
                )

                # Actions are now passed through the result
                actions = self.editor.take_actions()

            result = NotebookMutationResult(
                success=True,
                actions=actions,
                notebook_id=notebook_id,
                name=updated_title,
                message=f"Successfully updated notebook with title '{updated_title}'",
            )

            self.logger.info(f"Successfully updated notebook: {notebook_id}")

            # Update artifact if we have a chat session
            if title is not None:
                await self.link_artifact_to_session(
                    artifact_id=notebook_id,
                    artifact_type=ArtifactType.NOTEBOOK,
                    title=updated_title,
                    run_context=run_context,
                )

            return self._wrap_result(result)

        except Exception as e:
            error_msg = f"Failed to update notebook {notebook_id}: {e!s}"
            self.logger.error(error_msg, exc_info=True)

            error_result = NotebookMutationResult(
                success=False,
                notebook_id=notebook_id,
                message=f"Error updating notebook {notebook_id}: {error_msg}",
            )
            return self._wrap_result(error_result)

    @reads_artifact(NotebookListResult)
    async def list_notebooks(
        self, page_index: int = 1, page_size: int = 20, filter_string: str | None = None
    ) -> str:
        """List notebooks in project with pagination.

        :param page_index: Page number (1-indexed).
        :param page_size: Items per page.
        :param filter_string: Optional notebook name filter.
        """
        try:
            self.logger.info(
                f"Listing notebooks for project: {self.project_id} (page {page_index}, size {page_size})"
            )

            if not self.file_service:
                raise ValueError("File service is not available")

            # Get paginated notebooks for the project
            paginated_result = await self.file_service.get_notebooks(
                project_id=self.project_id,
                page_index=page_index,
                page_size=page_size,
                filter_string=filter_string,
            )

            # Extract items from paginated result
            notebooks = paginated_result.items
            total_count = paginated_result.total_count

            result = NotebookListResult(
                success=True,
                notebooks=notebooks,
                message=f"Successfully retrieved {len(notebooks)} notebooks from {total_count} total",
            )

            pages = (total_count + page_size - 1) // page_size if page_size > 0 else 1
            self.logger.info(
                f"Successfully retrieved {len(notebooks)} notebooks (page {page_index} of {pages})"
            )
            return self._wrap_result(result)

        except Exception as e:
            error_msg = f"Failed to list notebooks: {e!s}"
            self.logger.error(error_msg, exc_info=True)

            error_result = NotebookListResult(
                success=False, notebooks=[], message=f"Error listing notebooks: {error_msg}"
            )
            return self._wrap_result(error_result)

    @creates_artifact(
        NotebookMutationResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True
    )
    @validate_guids("notebook_id")
    async def duplicate_notebook(
        self,
        notebook_id: str,
        new_title: str | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Duplicate notebook.

        :param notebook_id: Source notebook ID.
        :param new_title: Optional new title.
        :param run_context: runtime context.
        """
        try:
            self.logger.info(f"Duplicating notebook: {notebook_id}")

            # Load the source notebook
            async with self._editor_lock:
                await self.editor.load_notebook_from_file(self.project_id, notebook_id)
                source_notebook = self.editor.get_notebook()

            # Determine the new title
            if new_title is None:
                new_title = f"Copy of {source_notebook.title}"

            # Check if the proposed name already exists and generate a unique name if needed
            final_title = self._generate_unique_notebook_name(new_title)

            # Create a complete copy of the source notebook
            new_notebook = source_notebook.model_copy(deep=True)

            # Update the title for the duplicate
            new_notebook.title = final_title

            # Generate a new ID for the duplicate (this will be set by the system when created)
            # The ID field will be auto-generated by the backend

            if not self.file_service:
                raise ValueError("File service is not available")

            # Create the new notebook as a resource
            response = await self.file_service.create_notebook(
                project_id=self.project_id, notebook=new_notebook, name=final_title
            )

            # Note: duplicate_notebook doesn't use editor, so no actions to set

            result = NotebookMutationResult(
                success=True,
                notebook_id=response.file.id,
                name=response.file.name,
                message=f"Successfully duplicated notebook '{source_notebook.title}' as '{final_title}'",
            )

            self.logger.info(f"Successfully duplicated notebook: {response.file.id}")

            # Register artifact if we have a chat session
            await self.link_artifact_to_session(
                artifact_id=response.file.id,
                artifact_type=ArtifactType.NOTEBOOK,
                title=response.file.name,
                run_context=run_context,
            )

            return self._wrap_result(result)

        except Exception as e:
            error_msg = f"Failed to duplicate notebook {notebook_id}: {e!s}"
            self.logger.error(error_msg, exc_info=True)

            error_result = NotebookMutationResult(
                success=False, message=f"Error duplicating notebook {notebook_id}: {error_msg}"
            )
            return self._wrap_result(error_result)

    def _generate_unique_notebook_name(self, base_name: str) -> str:
        """Generate unique notebook name with a short UID."""
        name, ext = os.path.splitext(base_name)
        short_id = str(uuid4())[:8]
        if ext:
            return f"{name}-{short_id}{ext}"
        return f"{name}-{short_id}"

    # Block Management Tools
    @updates_artifact(
        NotebookBlockResult,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Create Data Table",
        emit_tool_call=True,
    )
    @validate_guids("notebook_id")
    async def add_data_table(
        self,
        notebook_id: str,
        data_table_id: str,
        title: str | None = None,
        position: int | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Add a persistent SQL-backed block to the notebook.

        :param notebook_id: Notebook ID.
        :param data_table_id: Data table ID.
        :param title: Optional block title.
        :param position: Insert position (0-based index).
        :param run_context: runtime context.
        """

        async def create_block_op():
            notebook_block, effective_data_table_id = await self._build_data_table_block(
                data_table_id=data_table_id,
                title=title,
                run_context=run_context,
            )
            self.editor.add_block(notebook_block, position)

            return notebook_block, effective_data_table_id

        result, actions, error = await self._handle_operation(
            "Adding SQL block",
            self.project_id,
            notebook_id,
            create_block_op,
            run_context=run_context,
        )

        if error or result is None:
            error_detail = error or "Unknown error occurred"
            self.logger.error(f"Failed to add SQL block: {error_detail}")
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=None,
                block=None,
                error=error_detail,
                message=f"Error adding SQL block to notebook {notebook_id}",
            )

        # Unpack the result tuple (notebook_block, data_table_id)
        block, data_table_id = result

        return self._create_result(
            success=True,
            result_class=NotebookBlockResult,
            actions=actions,
            notebook_id=notebook_id,
            block_id=str(block.root.id),
            data_id=data_table_id,
            error=None,
            message=f"Successfully added SQL block. Data table ID: {data_table_id}",
        )

    @updates_artifact(
        NotebookBlockResult,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Add Paragraph",
        emit_tool_call=True,
    )
    @validate_guids("notebook_id")
    async def add_paragraph(
        self,
        notebook_id: str,
        text: str,
        position: int | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Add paragraph(s) to notebook. Supports Markdown.

        :param notebook_id: Notebook ID.
        :param text: Content (Plain text or Markdown).
        :param position: Insert position (0-based index).
        :param run_context: runtime context.
        """

        async def create_and_add_blocks():
            blocks = parse_markdown(text)

            # Fallback for empty or failed parsing
            if not blocks:
                # Should normally be handled by parser, but fallback to simple paragraph just in case
                paragraph_block_data = ParagraphBlockData(text=text)
                paragraph_block = ParagraphBlock(
                    id=str(uuid4()), type="paragraph", data=paragraph_block_data
                )
                blocks = [NotebookBlock(paragraph_block)]

            if len(blocks) == 1:
                self.editor.add_block(blocks[0], position)
                return blocks[0]
            else:
                self.editor.add_blocks(blocks, position)
                return blocks

        result, actions, error = await self._handle_operation(
            "Adding text",
            self.project_id,
            notebook_id,
            create_and_add_blocks,
            run_context=run_context,
        )

        if error or result is None:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=None,
                block=None,
                error=error,
                message=f"Error adding text to notebook {notebook_id}",
            )

        # Handle result type
        if isinstance(result, list):
            # Multi-block result
            block_ids = [str(b.root.id if hasattr(b, "root") else b.id) for b in result]
            return self._create_result(
                success=True,
                result_class=NotebookMultiBlockResult,
                actions=actions,
                notebook_id=notebook_id,
                block_ids=block_ids,
                blocks_count=len(result),
                error=None,
                message=f"Successfully added {len(result)} blocks to notebook {notebook_id}",
            )
        else:
            # Single block result
            return self._create_result(
                success=True,
                result_class=NotebookBlockResult,
                actions=actions,
                notebook_id=notebook_id,
                block_id=str(result.root.id),
                error=None,
                message=f"Successfully added text to notebook {notebook_id}",
            )

    @updates_artifact(
        NotebookBlockResult,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Add Mermaid Diagram",
        emit_tool_call=True,
    )
    @validate_guids("notebook_id")
    async def add_mermaid_diagram(
        self, notebook_id: str, code: str, title: str | None = None, position: int | None = None
    ) -> str:
        """Add a Mermaid diagram block to a notebook.

        :param notebook_id: Notebook ID.
        :param code: Mermaid source code.
        :param title: Optional diagram title.
        :param position: Insert position (0-based index).
        """

        def missing_code() -> str | None:
            if not code or not code.strip():
                return "Mermaid diagram code is required"
            return None

        def make_block():
            mermaid_block_data = MermaidBlockData(code=code, title=title or "Mermaid Diagram")
            return NotebookBlock(
                MermaidBlock(id=str(uuid4()), type="mermaid", data=mermaid_block_data)
            )

        return await self._add_simple_block(
            label="Mermaid diagram",
            make_block=make_block,
            notebook_id=notebook_id,
            success_message=f"Successfully added Mermaid diagram to notebook {notebook_id}",
            position=position,
            validate=missing_code,
        )

    @updates_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True)
    @validate_guids("notebook_id")
    async def add_list(
        self,
        notebook_id: str,
        items: list[str],
        style: str = "unordered",
        position: int | None = None,
    ) -> str:
        """Add list to notebook.

        :param notebook_id: Notebook ID.
        :param items: List items.
        :param style: unordered/ordered/checklist.
        :param position: Insert position (0-based index).
        """
        # Validate style
        list_style_val = (style or "").lower()
        if list_style_val not in ("unordered", "ordered", "checklist"):
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=None,
                block=None,
                error=f"Invalid list style: {style}. Must be 'unordered', 'ordered', or 'checklist'",
                message=f"Error adding list to notebook {notebook_id}",
            )
        list_style = ListStyle(list_style_val)

        async def create_and_add_block():
            # Convert items to the expected format using ListItem
            list_items = [
                ListItem(
                    content=item,
                    meta=ListItemMeta(checked=False)
                    if list_style == ListStyle.CHECKLIST
                    else ListItemMeta(),
                    items=[],
                )
                for item in items
            ]
            list_block_data = ListBlockData(
                style=list_style, items=list_items, meta=ListBlockMeta()
            )
            list_block = ListBlock(id=str(uuid4()), type="list", data=list_block_data)
            notebook_block = NotebookBlock(list_block)
            self.editor.add_block(notebook_block, position)
            return notebook_block

        block, actions, error = await self._handle_operation(
            "Adding list", self.project_id, notebook_id, create_and_add_block
        )

        if error or block is None:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=None,
                block=None,
                error=error,
                message=f"Error adding list to notebook {notebook_id}",
            )

        return self._create_result(
            success=True,
            result_class=NotebookBlockResult,
            actions=actions,
            notebook_id=notebook_id,
            block_id=str(block.root.id),
            error=None,
            message=f"Successfully added {style} list with {len(items)} items to notebook {notebook_id}",
        )

    @updates_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True)
    @validate_guids("notebook_id")
    async def add_quote(
        self, notebook_id: str, text: str, caption: str = "", position: int | None = None
    ) -> str:
        """Add quote to notebook.

        :param notebook_id: Notebook ID.
        :param text: Quote text.
        :param caption: Optional caption.
        :param position: Insert position (0-based index).
        """

        def make_block():
            # Generated model uses string with enum validation; default alignment is 'left'
            quote_block_data = QuoteBlockData(
                text=text, caption=caption, alignment=QuoteAlignment.LEFT
            )
            return NotebookBlock(QuoteBlock(id=str(uuid4()), type="quote", data=quote_block_data))

        return await self._add_simple_block(
            label="quote",
            make_block=make_block,
            notebook_id=notebook_id,
            success_message=f"Successfully added quote to notebook {notebook_id}",
            position=position,
        )

    @updates_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True)
    @validate_guids("notebook_id")
    async def add_table(
        self,
        notebook_id: str,
        content: list[list[str]],
        with_headings: bool = False,
        position: int | None = None,
    ) -> str:
        """Add table to notebook.

        :param notebook_id: Notebook ID.
        :param content: Table data (2D array).
        :param with_headings: First row as headers.
        :param position: Insert position (0-based index).
        """

        def make_block():
            table_block_data = TableBlockData(with_headings=with_headings, content=content)
            return NotebookBlock(TableBlock(id=str(uuid4()), type="table", data=table_block_data))

        return await self._add_simple_block(
            label="table",
            make_block=make_block,
            notebook_id=notebook_id,
            success_message=f"Successfully added table with {len(content)} rows to notebook {notebook_id}",
            position=position,
        )

    @updates_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True)
    @validate_guids("notebook_id")
    async def add_header(
        self, notebook_id: str, text: str, level: int = 2, position: int | None = None
    ) -> str:
        """Add header to notebook.

        :param notebook_id: Notebook ID.
        :param text: Header text.
        :param level: Level (2-5).
        :param position: Insert position (0-based index).
        """

        def make_block():
            validated_level = validate_header_level(level)
            header_block_data = HeaderBlockData(text=text, level=validated_level)
            return NotebookBlock(
                HeaderBlock(id=str(uuid4()), type="header", data=header_block_data)
            )

        return await self._add_simple_block(
            label="header",
            make_block=make_block,
            notebook_id=notebook_id,
            success_message=f"Successfully added header to notebook {notebook_id}",
            position=position,
        )

    @updates_artifact(
        NotebookMultiBlockResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True
    )
    @validate_guids("notebook_id")
    async def add_summary(
        self, notebook_id: str, title: str, points: list[str], position: int | None = None
    ) -> str:
        """Add summary (header + list) to notebook.

        :param notebook_id: Notebook ID.
        :param title: Summary title.
        :param points: Summary points.
        :param position: Insert position (0-based index).
        """

        async def create_and_add_summary():
            # Operate directly on the already-loaded editor to avoid nested load/save conflicts
            created_blocks: list[str] = []

            # 1) Add title as a header block (level 2)
            header_text = markdown_to_html(title)
            header_block_data = HeaderBlockData(text=header_text, level=2)
            header_block = HeaderBlock(id=str(uuid4()), type="header", data=header_block_data)
            header_nb_block = NotebookBlock(header_block)
            self.editor.add_block(header_nb_block, position)
            created_blocks.append(str(header_block.id))

            # Compute the actual index where the header was inserted
            blocks_after_header = self.editor.list_blocks()
            header_index = None
            for i, b in enumerate(blocks_after_header):
                br: Any = b.root if hasattr(b, "root") else b
                if str(br.id) == str(header_block.id):
                    header_index = i
                    break
            if header_index is None:
                # Fallback to last position if not found
                header_index = len(blocks_after_header) - 1

            # 2) Add points as an unordered list block immediately after the header
            list_insert_position = header_index + 1
            list_items = [
                ListItem(content=markdown_to_html(p), meta=ListItemMeta(), items=[])
                for p in (points or [])
            ]
            list_block_data = ListBlockData(
                style=ListStyle.UNORDERED, items=list_items, meta=ListBlockMeta()
            )
            list_block = ListBlock(id=str(uuid4()), type="list", data=list_block_data)
            list_nb_block = NotebookBlock(list_block)
            self.editor.add_block(list_nb_block, list_insert_position)
            created_blocks.append(str(list_block.id))

            return {"created_blocks": created_blocks}

        result, actions, error = await self._handle_operation(
            "Adding summary", self.project_id, notebook_id, create_and_add_summary
        )

        if error or result is None:
            return self._create_result(
                success=False,
                result_class=NotebookMultiBlockResult,
                notebook_id=notebook_id,
                error=error,
                message=f"Error adding summary to notebook {notebook_id}",
            )

        return self._create_result(
            success=True,
            result_class=NotebookMultiBlockResult,
            actions=actions,
            notebook_id=notebook_id,
            block_ids=result["created_blocks"],
            blocks_count=len(result["created_blocks"]),
            error=None,
            message=f"Successfully added summary with title '{title}' to notebook {notebook_id}",
        )

    @updates_artifact(
        NotebookBlockResult,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Edit Block",
        emit_tool_call=True,
    )
    @validate_guids("notebook_id", "block_id")
    async def edit_block(
        self,
        notebook_id: str,
        block_id: str,
        data: dict[str, Any],
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Edit block content in place.

        Pass the complete replacement block data as a flat camelCase object
        whose keys match the block type (the same shapes accepted by the
        ``add_*`` tools). Examples: ``{"text": "..."}`` for a paragraph,
        ``{"code": "...", "language": "python"}`` for a code block,
        ``{"withHeadings": true, "content": [["a"], ["b"]]}`` for a table, or a
        chart spec with ``config``/``dataRef`` for a chart block. Use
        ``edit_list_block`` for list blocks.

        :param notebook_id: Notebook ID.
        :param block_id: Block ID.
        :param data: Complete replacement block data.
        :param run_context: runtime context.
        """

        async def edit_operation():
            # Get the block to validate it exists
            block = self.editor.get_block(block_id)
            if not block:
                raise ValueError(f"Block {block_id} not found")

            # Validate the payload against the existing block's data contract on
            # the server. Accepting a plain object keeps the tool schema small
            # while preserving validation; a full block payload from get_block
            # ({"type": ..., "data": {...}}) is accepted too, using its data.
            # Programmatic callers may still pass a BlockData/data model.
            raw_data: Any = data
            if isinstance(raw_data, dict):
                payload = (
                    raw_data["data"]
                    if isinstance(raw_data.get("data"), dict) and "type" in raw_data
                    else raw_data
                )
                block_type = NotebookBlockType(block.root.type)
                data_model = _BLOCK_DATA_MODELS.get(block_type)
                if data_model is None:
                    raise ValueError(f"Editing block type '{block_type}' is not supported")
                actual_data = data_model.model_validate(payload)
            else:
                actual_data = getattr(raw_data, "root", raw_data)
            block_data = BlockData(actual_data)

            # Validate Python code before editing if it's a code block
            if (
                isinstance(actual_data, CodeBlockData)
                and actual_data.language.lower() == "python"
                and actual_data.code.strip()
            ):
                is_valid, issues = validate_python_code(actual_data.code)
                if not is_valid:
                    raise ValueError(f"Python code validation failed: {', '.join(issues)}")

            # A chart block must reference data attached to the notebook; attach
            # it on demand (same path as add_*_chart) so an edit cannot create a
            # chart whose data table is missing from the notebook.
            if isinstance(actual_data, ChartSpec) and actual_data.data_ref is not None:
                referenced_data_id = actual_data.data_ref.data_id
                if referenced_data_id:
                    effective_data_id, _ = await self._ensure_notebook_data_table(
                        referenced_data_id,
                        run_context=run_context,
                        title=f"Data for {actual_data.config.root.title}",
                    )
                    if effective_data_id != referenced_data_id:
                        actual_data.data_ref = actual_data.data_ref.model_copy(
                            update={"data_id": effective_data_id}
                        )

            # Edit the block with the provided BlockData
            self.editor.edit_block(block_id, block_data)
            return block

        block, actions, error = await self._handle_operation(
            f"Editing block {block_id}",
            self.project_id,
            notebook_id,
            edit_operation,
            run_context=run_context,
        )

        if error or block is None:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=block_id,
                error=error,
                message=f"Error editing block {block_id}",
            )

        return self._create_result(
            success=True,
            result_class=NotebookBlockResult,
            actions=actions,
            notebook_id=notebook_id,
            block_id=block_id,
            error=None,
            message=f"Successfully edited block {block_id}",
        )

    @updates_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK, emit_tool_call=True)
    @validate_guids("notebook_id", "block_id")
    async def edit_list_block(
        self,
        notebook_id: str,
        block_id: str,
        items: list[str],
        style: str = "unordered",
    ) -> str:
        """Edit a list block's items.

        ``edit_block`` cannot accept list payloads (its schema intentionally
        excludes the recursive ListBlockData), so list/summary blocks have this
        dedicated editing tool instead.

        :param notebook_id: Notebook ID.
        :param block_id: Block ID of the list block to edit.
        :param items: Replacement list items.
        :param style: unordered/ordered/checklist.
        """

        list_style_val = (style or "").lower()
        if list_style_val not in ("unordered", "ordered", "checklist"):
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=block_id,
                block=None,
                error=f"Invalid list style: {style}. Must be 'unordered', 'ordered', or 'checklist'",
                message=f"Error editing list block {block_id}",
            )
        list_style = ListStyle(list_style_val)

        async def edit_operation():
            block = self.editor.get_block(block_id)
            if not block:
                raise ValueError(f"Block {block_id} not found")

            list_items = [
                ListItem(
                    content=item,
                    meta=ListItemMeta(checked=False)
                    if list_style == ListStyle.CHECKLIST
                    else ListItemMeta(),
                    items=[],
                )
                for item in items
            ]
            block_data = BlockData(
                ListBlockData(
                    style=list_style,
                    items=list_items,
                    meta=ListBlockMeta(),
                )
            )
            self.editor.edit_block(block_id, block_data)
            return self.editor.get_block(block_id)

        block, actions, error = await self._handle_operation(
            f"Editing list block {block_id}", self.project_id, notebook_id, edit_operation
        )

        if error or block is None:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=block_id,
                block=None,
                error=error,
                message=f"Error editing list block {block_id}",
            )

        return self._create_result(
            success=True,
            result_class=NotebookBlockResult,
            actions=actions,
            notebook_id=notebook_id,
            block_id=block_id,
            block=block,
            error=None,
            message=f"Successfully edited list block {block_id} with {len(items)} items",
        )

    @deletes_artifact(
        NotebookBlockResult,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Delete Block",
        emit_tool_call=True,
    )
    @validate_guids("notebook_id", "block_id")
    async def delete_block(self, notebook_id: str, block_id: str) -> str:
        """Delete block from notebook.

        :param notebook_id: Notebook ID.
        :param block_id: Block ID.
        """

        async def delete_operation():
            self.editor.delete_block(block_id)

        _, actions, error = await self._handle_operation(
            f"Deleting block {block_id}", self.project_id, notebook_id, delete_operation
        )

        if error:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=block_id,
                error=error,
                message=f"Error deleting block {block_id}",
            )

        return self._create_result(
            success=True,
            result_class=NotebookBlockResult,
            actions=actions,
            notebook_id=notebook_id,
            block_id=block_id,
            error=None,
            message=f"Successfully deleted block {block_id}",
        )

    @deletes_artifact(
        NotebookMultiBlockResult,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Delete Blocks",
        emit_tool_call=True,
    )
    @validate_guids("notebook_id")
    async def delete_blocks(self, notebook_id: str, block_ids: list[str]) -> str:
        """Delete several blocks from a notebook in one call.

        Prefer this over repeating ``delete_block`` when removing multiple
        blocks (for example after replacing a section of the notebook).

        :param notebook_id: Notebook ID.
        :param block_ids: Block IDs to delete.
        """
        if not block_ids:
            return self._create_result(
                success=False,
                result_class=NotebookMultiBlockResult,
                notebook_id=notebook_id,
                block_ids=[],
                blocks_count=0,
                message="No block IDs provided.",
            )
        for block_id in block_ids:
            validate_guid(block_id, "block_id")

        async def delete_operation() -> list[str]:
            before = {str(block.root.id) for block in self.editor.list_blocks()}
            for block_id in block_ids:
                self.editor.delete_block(block_id)
            after = {str(block.root.id) for block in self.editor.list_blocks()}
            return [
                block_id for block_id in block_ids if block_id in before and block_id not in after
            ]

        deleted, actions, error = await self._handle_operation(
            f"Deleting {len(block_ids)} blocks",
            self.project_id,
            notebook_id,
            delete_operation,
        )

        if error or deleted is None:
            return self._create_result(
                success=False,
                result_class=NotebookMultiBlockResult,
                notebook_id=notebook_id,
                block_ids=[],
                blocks_count=0,
                error=error or "Failed to delete blocks",
                message=f"Error deleting blocks from notebook {notebook_id}",
            )

        return self._create_result(
            success=True,
            result_class=NotebookMultiBlockResult,
            actions=actions,
            notebook_id=notebook_id,
            block_ids=deleted,
            blocks_count=len(deleted),
            error=None,
            message=(
                f"Successfully deleted {len(deleted)} of {len(block_ids)} block(s) "
                f"from notebook {notebook_id}"
            ),
        )

    @reads_artifact(NotebookBlockListResult, artifact_type=ArtifactType.NOTEBOOK)
    @validate_guids("notebook_id")
    async def list_blocks(self, notebook_id: str) -> str:
        """List blocks in notebook.

        :param notebook_id: Notebook ID.
        """
        try:
            self.logger.info(f"Listing blocks in notebook: {notebook_id}")
            async with self._editor_lock:
                await self.editor.load_notebook_from_file(self.project_id, notebook_id)
                blocks = self.editor.list_blocks()
            self.logger.info(f"Successfully retrieved {len(blocks)} blocks")
            return self._create_result(
                success=True,
                result_class=NotebookBlockListResult,
                notebook_id=notebook_id,
                blocks=blocks,
                blocks_count=len(blocks),
                error=None,
                message=f"Successfully retrieved {len(blocks)} blocks from notebook {notebook_id}",
            )
        except Exception as e:
            error_msg = f"Failed to list blocks in notebook {notebook_id}: {e!s}"
            self.logger.error(error_msg, exc_info=True)
            return self._create_result(
                success=False,
                result_class=NotebookBlockListResult,
                notebook_id=notebook_id,
                blocks=[],
                error=error_msg,
                message=f"Error listing blocks in notebook {notebook_id}",
            )

    @tool_meta(display_name="Get Notebook Outline", emit_tool_call=True)
    @validate_guids("notebook_id")
    async def get_notebook_outline(self, notebook_id: str) -> str:
        """Return a compact outline of notebook blocks without their payloads.

        Use this instead of ``list_blocks`` when you only need to know which
        blocks exist and where (id/type/title). ``list_blocks`` returns full
        block data, which is large; follow up with ``get_block``/``get_blocks``
        for the specific blocks whose contents you need.

        :param notebook_id: Notebook ID.
        """
        try:
            async with self._editor_lock:
                await self.editor.load_notebook_from_file(self.project_id, notebook_id)
                blocks = self.editor.list_blocks()
            outline = []
            for block in blocks:
                root = block.root
                outline.append(
                    {
                        "blockId": str(root.id),
                        "type": getattr(root.type, "value", root.type),
                        "title": getattr(root.data, "title", None),
                    }
                )
            return json.dumps(
                {
                    "success": True,
                    "notebookId": notebook_id,
                    "blocksCount": len(outline),
                    "blocks": outline,
                    "message": (
                        f"Notebook {notebook_id} has {len(outline)} block(s); "
                        "use get_block/get_blocks for block contents."
                    ),
                },
                ensure_ascii=True,
            )
        except Exception as exc:
            self.logger.error(f"Failed to build notebook outline for {notebook_id}: {exc}")
            return json.dumps(
                {
                    "success": False,
                    "notebookId": notebook_id,
                    "error": f"Failed to build notebook outline: {exc}",
                },
                ensure_ascii=True,
            )

    @validate_guids("notebook_id", "block_id")
    @reads_artifact(NotebookBlockResult, artifact_type=ArtifactType.NOTEBOOK)
    async def get_block(self, notebook_id: str, block_id: str) -> str:
        """Get specific block.

        :param notebook_id: Notebook ID.
        :param block_id: Block ID.
        """
        try:
            self.logger.info(f"Getting block {block_id} from notebook: {notebook_id}")
            async with self._editor_lock:
                await self.editor.load_notebook_from_file(self.project_id, notebook_id)
                block = self.editor.get_block(block_id)
            if not block:
                raise ValueError(f"Block {block_id} not found")
            self.logger.info(f"Successfully retrieved block: {block_id}")
            return self._create_result(
                success=True,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=block_id,
                block=block,
                error=None,
                message=f"Successfully retrieved block {block_id}",
            )
        except Exception as e:
            error_msg = f"Failed to get block {block_id}: {e!s}"
            self.logger.error(error_msg, exc_info=True)
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=block_id,
                block=None,
                error=error_msg,
                message=f"Error getting block {block_id}",
            )

    @tool_meta(NotebookBlockBatchResult, display_name="Get Blocks (Batch)", emit_tool_call=True)
    async def get_blocks(self, notebook_id: str, block_ids: list[str]) -> str:
        """Retrieve several blocks from one notebook in a single call.

        :param notebook_id: Notebook ID.
        :param block_ids: Block IDs to retrieve.
        """
        blocks = await self._collect_batch_items(
            block_ids,
            fetch=lambda block_id: self.get_block(notebook_id, block_id),
            parse_into=NotebookBlockResult,
            failure=lambda block_id, exc: NotebookBlockResult(
                success=False,
                notebook_id=notebook_id,
                block_id=block_id,
                block=None,
                message=str(exc),
            ),
        )
        failed_count = self._failed_count(blocks)
        return self._wrap_result(
            NotebookBlockBatchResult(
                success=bool(blocks) and failed_count == 0,
                message=f"Retrieved {len(blocks)} block(s); {failed_count} failed.",
                blocks=blocks,
                blocks_count=len(blocks),
                failed_count=failed_count,
            )
        )
