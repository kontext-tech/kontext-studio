"""NotebookTools core: editor handle, editor lock, operation executor, and
shared data-table/handle plumbing."""

import asyncio
from contextlib import suppress
from uuid import uuid4

from kontext.agent import RuntimeToolContext
from kontext.common.protocols import (
    IFileServiceProtocol,
    IQuerySessionServiceProtocol,
)
from kontext.common.python_execution.helpers import (
    extract_kontext_load_data_ids,
    is_kontext_data_alias,
)
from kontext.execution import PythonExecutionService
from kontext.file.notebook.editor import NotebookEditor
from kontext.schema import (
    ArtifactType,
    CodeExecutionOutput,
    CodeLanguage,
    DataRef,
    InlineData,
    NotebookBlock,
    NotebookDocument,
    PythonExecutionTargetType,
    SqlBlock,
    SqlBlockData,
)

from ..kontext_toolkit import KontextToolkit

"""NotebookTools core: constructor, editor handle, editor lock, operation
executor, and the shared data-table/handle plumbing."""

type ChartFieldValue = str | list[str]
type ChartFieldInputs = dict[str, str] | dict[str, ChartFieldValue]


def _validate_distinct_pie_fields(angle_field: str, color_field: str) -> None:
    """Value (angle) and category (color) fields must differ for a pie chart."""
    if angle_field == color_field:
        raise ValueError("Value field (angle) and Category field (color) must be different")


class NotebookCoreMixin(KontextToolkit):
    """Editor handle, editor lock, operation executor, and shared data plumbing.

    The concrete `NotebookTools` class owns the constructor; the attributes it
    builds are declared here so every mixin type-checks against them.
    """

    editor: NotebookEditor
    file_service: IFileServiceProtocol | None
    query_session_service: IQuerySessionServiceProtocol | None
    python_execution_service: PythonExecutionService
    allow_python_blocks: bool
    allow_python_execution_persistence: bool
    _editor_lock: asyncio.Lock

    async def _resolve_notebook_id(
        self,
        notebook_id: str | None,
        run_context: RuntimeToolContext | None = None,
    ) -> tuple[str, bool, str | None]:
        """Resolve an omitted ``notebook_id`` against the chat session's linked notebooks.

        Long-args block tools occasionally drop a required leading parameter
        while the model fills in the large ``code`` payload. Every notebook
        mutation links its artifact back to the chat session, so an omitted
        ``notebook_id`` is recoverable: exactly one linked notebook resolves to
        it; none fails with recoverable guidance; several fails listing the
        choices (mutations never guess).

        Returns ``(resolved_id_or_empty, defaulted, error_or_None)``
        — on error the id is ``""``.
        """
        if notebook_id:
            return notebook_id, False, None

        notebooks: dict[str, str | None] = {}
        shared_store = self.get_shared_session_store(run_context)
        if shared_store is not None:
            notebooks = {
                descriptor.artifact_id: descriptor.title
                for descriptor in shared_store.list_artifact_descriptors(
                    artifact_type=ArtifactType.NOTEBOOK
                )
            }
        if not notebooks and self.chat_session_id:
            chat_service = (
                self.runtime_provider.get_chat_session_service()
                if self.runtime_provider is not None
                else None
            )
            if chat_service is not None:
                try:
                    artifacts = await chat_service.list_artifacts(str(self.chat_session_id))
                except Exception as exc:
                    self.logger.warning(
                        "Failed to list chat session artifacts for notebook_id resolution: %s",
                        exc,
                    )
                    artifacts = []
                for artifact in artifacts:
                    if artifact.artifact_type == ArtifactType.NOTEBOOK:
                        notebooks[str(artifact.artifact_id)] = artifact.title

        if not notebooks:
            return (
                "",
                True,
                (
                    "notebook_id is required: no notebook is linked to this chat session yet. "
                    "Create one with `create_notebook` and use its returned ID, or pass an "
                    "existing notebook's ID explicitly."
                ),
            )

        if len(notebooks) > 1:
            listed = "; ".join(
                f"{artifact_id} ('{title}')" if title else artifact_id
                for artifact_id, title in sorted(notebooks.items())
            )
            return (
                "",
                True,
                (
                    f"notebook_id is required: {len(notebooks)} notebooks are linked to this "
                    f"chat session ({listed}). Pass notebook_id explicitly to choose one."
                ),
            )

        resolved = next(iter(notebooks))
        return resolved, True, None

    async def _handle_operation(
        self,
        operation_name: str,
        project_id: str,
        notebook_id: str,
        operation_func,
        run_context: RuntimeToolContext | None = None,
    ):
        """Handle notebook operations with persistence and action context management."""
        try:
            self.logger.info(f"{operation_name} in notebook: {notebook_id} (project: {project_id})")
            async with self._editor_lock:
                await self.editor.load_notebook_from_file(project_id, notebook_id)
                result = await operation_func()
                await self.editor.save_notebook(project_id, notebook_id)
                actions = self.editor.take_actions()
                action_count = len(actions)

            # Update artifact session state (e.g. modifiedAt)
            if run_context:
                await self.link_artifact_to_session(
                    artifact_id=notebook_id,
                    artifact_type=ArtifactType.NOTEBOOK,
                    run_context=run_context,
                )

            # Actions were taken under the lock so concurrent operations on
            # the same toolkit cannot steal or lose each other's actions.
            self.logger.info(f"Actions taken from editor: {action_count} actions")
            for i, action in enumerate(actions):
                self.logger.info(
                    f"  Action {i}: {action.root.action_type if hasattr(action.root, 'action_type') else type(action.root).__name__}"
                )

            self.logger.info(f"Successfully {operation_name.lower()} in notebook: {notebook_id}")
            return result, actions, None
        except Exception as e:
            error_msg = f"Failed to {operation_name.lower()} in notebook {notebook_id}: {e!s}"
            self.logger.error(error_msg, exc_info=True)
            # Clear any pending actions on error
            with suppress(Exception):
                self.editor.take_actions()
            return None, None, error_msg

    @staticmethod
    def _collect_notebook_sql_data_table_ids(notebook: NotebookDocument) -> set[str]:
        data_table_ids: set[str] = set()
        for block in notebook.blocks:
            root = block.root
            if not isinstance(root, SqlBlock):
                continue
            data_ref = getattr(root.data, "data_ref", None)
            data_table_id = getattr(data_ref, "data_id", None)
            if data_table_id:
                data_table_ids.add(str(data_table_id))
        return data_table_ids

    async def _build_data_table_block(
        self,
        *,
        data_table_id: str,
        title: str | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> tuple[NotebookBlock, str]:
        effective_data_table_id = data_table_id
        descriptor = self.get_artifact_descriptor(data_table_id, run_context)
        final_sql = (
            descriptor.sql
            if descriptor and descriptor.artifact_type == ArtifactType.DATATABLE
            else None
        )

        if not final_sql:
            try:
                effective_data_table_id = await self.resolve_data_table_id(
                    data_table_id,
                    run_context=run_context,
                )
                descriptor = self.get_artifact_descriptor(
                    effective_data_table_id,
                    run_context,
                )
                if descriptor and descriptor.artifact_type == ArtifactType.DATATABLE:
                    final_sql = descriptor.sql

                file_service = self.get_file_service()
                if file_service:
                    content = await file_service.get_file_content(
                        self.project_id,
                        effective_data_table_id,
                    )
                    InlineData.model_validate_json(content)
            except Exception as e:
                raise ValueError(
                    f"Data table '{data_table_id}' could not be resolved: {e!s}"
                ) from e

        if not final_sql:
            final_sql = f"-- Data table reference: {effective_data_table_id}"

        sql_block_data = SqlBlockData(
            code=final_sql,
            data_ref=DataRef(
                data_id=effective_data_table_id,
                code=final_sql,
                language=CodeLanguage.SQL,
            ),
            is_executing=False,
            title=title,
        )
        sql_block = SqlBlock(
            id=str(uuid4()),
            type="sql",
            data=sql_block_data,
        )
        return NotebookBlock(sql_block), effective_data_table_id

    def _replace_python_data_table_id(
        self,
        code: str,
        *,
        original_data_table_id: str,
        effective_data_table_id: str,
    ) -> str:
        if original_data_table_id == effective_data_table_id:
            return code

        return code.replace(
            f"'{original_data_table_id}'",
            f"'{effective_data_table_id}'",
        ).replace(
            f'"{original_data_table_id}"',
            f'"{effective_data_table_id}"',
        )

    async def _materialize_python_data_tables(
        self,
        *,
        code: str,
        run_context: RuntimeToolContext | None = None,
        insert_position: int | None = None,
    ) -> tuple[str, int]:
        # Aliases resolve per notebook at execution; only durable table ids
        # (UUIDs) get data-table blocks materialized for them.
        referenced_data_table_ids = [
            name for name in extract_kontext_load_data_ids(code) if not is_kontext_data_alias(name)
        ]
        if not referenced_data_table_ids:
            return code, 0

        notebook = self.editor.get_notebook()
        existing_data_table_ids = self._collect_notebook_sql_data_table_ids(notebook)
        effective_code = code
        next_position = insert_position
        inserted_count = 0

        for referenced_data_table_id in referenced_data_table_ids:
            effective_data_table_id = referenced_data_table_id
            if referenced_data_table_id not in existing_data_table_ids:
                block, effective_data_table_id = await self._build_data_table_block(
                    data_table_id=referenced_data_table_id,
                    run_context=run_context,
                )
                self.editor.add_block(block, next_position)
                if next_position is not None:
                    next_position += 1
                existing_data_table_ids.add(effective_data_table_id)
                inserted_count += 1

            effective_code = self._replace_python_data_table_id(
                effective_code,
                original_data_table_id=referenced_data_table_id,
                effective_data_table_id=effective_data_table_id,
            )

        return effective_code, inserted_count

    async def _resolve_managed_python_execution(
        self,
        *,
        execution_run_id: str,
        expected_target_type: PythonExecutionTargetType,
    ) -> tuple[str, list[CodeExecutionOutput], int]:
        execution_result = await self.python_execution_service.get_execution_result_async(
            project_id=self.project_id,
            run_id=execution_run_id,
        )
        resolved_code = execution_result.code
        if not resolved_code or not resolved_code.strip():
            raise ValueError(
                f"Managed Python execution run {execution_run_id} does not contain executable code."
            )

        actual_target_type = execution_result.python_result.target_type
        if actual_target_type != expected_target_type:
            if expected_target_type == PythonExecutionTargetType.SESSION:
                raise ValueError(
                    "Execution run "
                    f"{execution_run_id} is notebook-backed. Use `persist_python_execution_state` "
                    "for notebook block reruns."
                )
            raise ValueError(
                "Execution run "
                f"{execution_run_id} is session-scoped. Use `import_executed_python` "
                "for notebook authoring imports."
            )

        executed_at = (
            execution_result.execution_run.completed_at
            or execution_result.execution_run.started_at
            or execution_result.execution_run.created_at
        )
        return (
            resolved_code,
            list(execution_result.python_result.outputs),
            int(executed_at.timestamp() * 1000),
        )

    async def _validate_chart_fields(
        self, data_table_id: str, required_fields: ChartFieldInputs
    ) -> list[str]:
        """
        Validate that all required fields are valid for chart creation.

        Args:
            data_table_id: The data table ID to validate against
            required_fields: Dictionary of field names to validate

        Returns:
            List of validation error messages (empty if all valid)

        Raises:
            ValueError: If the data table is not found
        """
        # Register transient data in editor if available so validation works
        transient_data = self.get_transient_data(data_table_id)
        if transient_data:
            self.editor.register_data_table(transient_data, data_table_id)

        # Use the editor's validation method
        return await self.editor.validate_chart_fields(data_table_id, required_fields)

    async def _prepare_chart_data_table(
        self, data_table_id: str
    ) -> tuple[DataRef | None, InlineData | None]:
        """
        Prepare chart data table parameters based on row count and thresholds.

        If row count <= DOCUMENT_EMBEDDING_THRESHOLD (50) and it's transient,
        it will be embedded. If it's large or already a file, it will be referenced.

        Args:
            data_table_id: Data table ID (can be transient UUID or file ID)

        Returns:
            tuple of (data_ref, inline_data)
        """
        # For notebook chart blocks, ALWAYS attach a data_table_id via DataRef.
        # This makes charts stable/refreshable and prevents accidental re-promotion creating
        # a different file id than the SQL block is using.
        data_source = await self.editor.fetch_data_table(data_table_id)
        resolved_id = await self.resolve_data_table_id(data_table_id)
        return (
            DataRef(
                data_id=resolved_id,
            ),
            data_source,
        )

    async def _ensure_notebook_data_table(
        self,
        data_table_id: str,
        *,
        run_context: RuntimeToolContext | None = None,
        title: str | None = None,
        position: int | None = None,
    ) -> tuple[str, bool]:
        """Ensure a data table is attached to the notebook as a SQL block.

        Charts reference their data through a SQL block's ``data_ref.data_id``.
        Creating a chart for a data table that has not been attached yet used to
        fail with ``Data table <id> not found in notebook``. Mirror
        ``add_data_table`` / ``import_chart`` / Python data-table
        materialization by attaching the missing block automatically instead of
        forcing the caller to add the data table first.

        Args:
            data_table_id: Data table handle (durable file ID or transient ID).
            run_context: runtime context for session-state resolution.
            title: Optional title for the auto-created SQL block.
            position: Optional insert position for the auto-created SQL block.

        Returns:
            tuple of (effective_data_table_id, inserted). ``inserted`` is True
            when a new SQL block was added at ``position``.

        Raises:
            ValueError: If the data table cannot be resolved or materialized.
        """
        existing_data_table_ids = self._collect_notebook_sql_data_table_ids(
            self.editor.get_notebook()
        )
        if data_table_id in existing_data_table_ids:
            return data_table_id, False

        block, effective_data_table_id = await self._build_data_table_block(
            data_table_id=data_table_id,
            title=title,
            run_context=run_context,
        )

        # ``_build_data_table_block`` may resolve a transient handle to a durable
        # file ID that is already attached; never duplicate an existing block.
        if effective_data_table_id in existing_data_table_ids:
            return effective_data_table_id, False

        self.editor.add_block(block, position)
        return effective_data_table_id, True
