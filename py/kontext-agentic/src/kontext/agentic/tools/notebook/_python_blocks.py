"""Python-block tools for NotebookTools (draft blocks, executed-state import/persistence)."""

from collections.abc import Callable

from kontext.agent import RuntimeToolContext
from kontext.agent.tools import (
    updates_artifact,
)
from kontext.agentic.utils.guid_validation import validate_guid, validate_guids
from kontext.common.python_execution.policy import validate_python_code
from kontext.schema import (
    ArtifactType,
    CodeBlock,
    NotebookBlock,
    NotebookBlockResult,
    PythonExecutionTargetType,
)

from ._core import NotebookCoreMixin

"""Python-block tools (draft blocks, executed-state import/persistence)."""


class NotebookPythonBlocksMixin(NotebookCoreMixin):
    def _load_python_code_block(self, block_id: str) -> CodeBlock:
        """Fetch a block and assert it is an existing Python code block."""
        existing_block = self.editor.get_block(block_id)
        if existing_block is None:
            raise ValueError(f"Block {block_id} not found")

        block_root = existing_block.root
        if not isinstance(block_root, CodeBlock):
            raise ValueError(f"Block {block_id} is not a code block")

        block_language = getattr(block_root.data.language, "value", block_root.data.language)
        if str(block_language).lower() != "python":
            raise ValueError(f"Block {block_id} is not a Python block")
        return block_root

    async def _add_simple_block(
        self,
        *,
        label: str,
        make_block: Callable[[], NotebookBlock],
        notebook_id: str,
        success_message: str,
        position: int | None = None,
        run_context: RuntimeToolContext | None = None,
        validate: Callable[[], str | None] | None = None,
    ) -> str:
        """Shared create-and-add pipeline for simple single-block tools.

        `validate` runs before any state mutation and returns an error string
        (or None); its failure surfaces as the tool's structured error result.
        """

        if validate is not None and (validation_error := validate()):
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=None,
                block=None,
                error=validation_error,
                message=f"Error adding {label} to notebook {notebook_id}",
            )

        async def create_and_add_block():
            block = make_block()
            self.editor.add_block(block, position)
            return block

        block, actions, error = await self._handle_operation(
            f"Adding {label}",
            self.project_id,
            notebook_id,
            create_and_add_block,
            run_context=run_context,
        )

        if error or block is None:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=None,
                block=None,
                error=error,
                message=f"Error adding {label} to notebook {notebook_id}",
            )

        return self._create_result(
            success=True,
            result_class=NotebookBlockResult,
            actions=actions,
            notebook_id=notebook_id,
            block_id=str(block.root.id),
            error=None,
            message=success_message,
        )

    @updates_artifact(
        NotebookBlockResult,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Add Python Block",
        emit_tool_call=True,
    )
    @validate_guids("notebook_id")
    async def add_python(
        self,
        notebook_id: str | None = None,
        code: str = "",
        title: str | None = None,
        position: int | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Add a Python code block to the notebook.

        :param notebook_id: Notebook ID. Optional: when omitted, defaults to the
            chat session's single linked notebook; pass it explicitly when more
            than one notebook is linked.
        :param code: Python code content.
        :param title: Optional title for the code block.
        :param position: Insert position (0-based index).
        :param run_context: runtime context.
        """
        notebook_id, _defaulted, resolution_error = await self._resolve_notebook_id(
            notebook_id, run_context
        )
        if resolution_error is not None:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id="",
                block_id=None,
                block=None,
                error=resolution_error,
                message="Error adding Python block",
            )

        if not self.allow_python_blocks:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=None,
                block=None,
                error="Python block mutation is not enabled in this notebook runtime.",
                message=f"Error adding Python block to notebook {notebook_id}",
            )

        if not code or not code.strip():
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=None,
                block=None,
                error="Python code is required",
                message=f"Error adding Python block to notebook {notebook_id}",
            )

        # Validate code before adding
        is_valid, issues = validate_python_code(code)
        if not is_valid:
            error_msg = f"Python code validation failed: {', '.join(issues)}"
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=None,
                block=None,
                error=error_msg,
                message=f"Error adding Python block to notebook {notebook_id}",
            )

        async def create_and_add_block():
            self.logger.info(f"Adding Python block to notebook: {notebook_id}")
            effective_code, inserted_count = await self._materialize_python_data_tables(
                code=code,
                run_context=run_context,
                insert_position=position,
            )
            notebook_block = self.editor.add_code_block(
                effective_code,
                language="python",
                position=(position + inserted_count if position is not None else None),
                title=title,
            )
            return notebook_block

        block, actions, error = await self._handle_operation(
            "Adding Python block",
            self.project_id,
            notebook_id,
            create_and_add_block,
            run_context=run_context,
        )

        if error or block is None:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=None,
                block=None,
                error=error or "Failed to add Python block",
                message=f"Error adding Python block to notebook {notebook_id}",
            )

        success_notebook_clause = (
            f" (notebook_id omitted; resolved to the chat session's linked notebook {notebook_id})"
            if _defaulted
            else ""
        )
        return self._create_result(
            success=True,
            result_class=NotebookBlockResult,
            actions=actions,
            notebook_id=notebook_id,
            block_id=str(block.root.id),
            error=None,
            message=f"Successfully added Python block to notebook {notebook_id}{success_notebook_clause}",
        )

    @updates_artifact(
        NotebookBlockResult,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Import Executed Python",
        emit_tool_call=True,
    )
    @validate_guids("notebook_id", "execution_run_id")
    async def import_executed_python(
        self,
        execution_run_id: str,
        notebook_id: str | None = None,
        title: str | None = None,
        block_id: str | None = None,
        position: int | None = None,
        last_executed: int | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Create or update a notebook Python block from a managed execution run.

        Use this after Python Agent has already validated and executed the final
        notebook-targeted code with `execute_python_script(...)`.

        :param execution_run_id: Managed Python execution run ID to import.
        :param notebook_id: Notebook ID. Optional: when omitted, defaults to the
            chat session's single linked notebook; pass it explicitly when more
            than one notebook is linked.
        :param title: Optional title for the Python block.
        :param block_id: Optional existing Python block ID to overwrite.
        :param position: Insert position for a new block (0-based index).
        :param last_executed: Optional execution timestamp override in milliseconds.
        :param run_context: runtime context.
        """
        notebook_id, _defaulted, resolution_error = await self._resolve_notebook_id(
            notebook_id, run_context
        )
        if resolution_error is not None:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id="",
                block_id=block_id,
                block=None,
                error=resolution_error,
                message="Error importing executed Python",
            )

        if not self.allow_python_blocks or not self.allow_python_execution_persistence:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=block_id,
                block=None,
                error="Executed Python import is not enabled in this notebook runtime.",
                message=f"Error importing executed Python into notebook {notebook_id}",
            )

        if block_id is not None:
            validate_guid(block_id, "block_id")

        try:
            (
                resolved_code,
                resolved_outputs,
                resolved_last_executed,
            ) = await self._resolve_managed_python_execution(
                execution_run_id=execution_run_id,
                expected_target_type=PythonExecutionTargetType.SESSION,
            )
        except Exception as exc:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=block_id,
                block=None,
                error=str(exc),
                message=f"Error importing executed Python into notebook {notebook_id}",
            )

        is_valid, issues = validate_python_code(resolved_code)
        if not is_valid:
            error_msg = f"Python code validation failed: {', '.join(issues)}"
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=block_id,
                block=None,
                error=error_msg,
                message=f"Error importing executed Python into notebook {notebook_id}",
            )

        async def import_operation():
            effective_last_executed = last_executed or resolved_last_executed

            if block_id is not None:
                block_root = self._load_python_code_block(block_id)

                block_index = next(
                    (
                        index
                        for index, notebook_block in enumerate(self.editor.get_notebook().blocks)
                        if str(notebook_block.root.id) == block_id
                    ),
                    None,
                )
                if block_index is None:
                    raise ValueError(f"Block {block_id} not found in notebook state")

                effective_code, _inserted_count = await self._materialize_python_data_tables(
                    code=resolved_code,
                    run_context=run_context,
                    insert_position=block_index,
                )
                self.editor.edit_code_block(
                    block_id,
                    code=effective_code,
                    language="python",
                    title=title if title is not None else block_root.data.title,
                )
                target_block_id = block_id
            else:
                effective_code, inserted_count = await self._materialize_python_data_tables(
                    code=resolved_code,
                    run_context=run_context,
                    insert_position=position,
                )
                created_block = self.editor.add_code_block(
                    effective_code,
                    language="python",
                    position=(position + inserted_count if position is not None else None),
                    title=title,
                )
                target_block_id = str(created_block.root.id)

            return self.editor.update_code_block_execution(
                target_block_id,
                outputs=resolved_outputs,
                is_executing=False,
                last_executed=effective_last_executed,
            )

        block, actions, error = await self._handle_operation(
            "Importing executed Python into notebook",
            self.project_id,
            notebook_id,
            import_operation,
            run_context=run_context,
        )

        if error or block is None:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=block_id,
                block=None,
                error=error or "Failed to import executed Python",
                message=f"Error importing executed Python into notebook {notebook_id}",
            )

        return self._create_result(
            success=True,
            result_class=NotebookBlockResult,
            actions=actions,
            notebook_id=notebook_id,
            block_id=str(block.root.id),
            block=block,
            error=None,
            message=f"Successfully imported executed Python into notebook {notebook_id}",
        )

    @updates_artifact(
        NotebookBlockResult,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Persist Python Execution State",
        emit_tool_call=True,
    )
    @validate_guids("notebook_id", "block_id", "execution_run_id")
    async def persist_python_execution_state(
        self,
        block_id: str,
        execution_run_id: str,
        notebook_id: str | None = None,
        title: str | None = None,
        is_executing: bool = False,
        last_executed: int | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Persist managed notebook Python execution state back onto a notebook block.

        :param notebook_id: Notebook ID. Optional: when omitted, defaults to the
            chat session's single linked notebook; pass it explicitly when more
            than one notebook is linked.
        :param block_id: Block ID.
        :param execution_run_id: Managed notebook execution run ID to persist.
        :param title: Optional final title to persist with the block.
        :param is_executing: Whether the block should remain marked as executing.
        :param last_executed: Optional execution timestamp override in milliseconds.
        :param run_context: runtime context.
        """
        notebook_id, _defaulted, resolution_error = await self._resolve_notebook_id(
            notebook_id, run_context
        )
        if resolution_error is not None:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id="",
                block_id=block_id,
                error=resolution_error,
                message="Error persisting Python execution state",
            )

        if not self.allow_python_execution_persistence:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=block_id,
                error="Python execution persistence is not enabled in this notebook runtime.",
                message=f"Error persisting Python execution state for block {block_id} in notebook {notebook_id}",
            )

        try:
            (
                resolved_code,
                resolved_outputs,
                resolved_last_executed,
            ) = await self._resolve_managed_python_execution(
                execution_run_id=execution_run_id,
                expected_target_type=PythonExecutionTargetType.NOTEBOOK,
            )
        except Exception as exc:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=block_id,
                error=str(exc),
                message=f"Error persisting Python execution state for block {block_id} in notebook {notebook_id}",
            )

        async def persist_operation():
            block_root = self._load_python_code_block(block_id)

            effective_title = title if title is not None else block_root.data.title
            effective_code = resolved_code
            if effective_code != block_root.data.code or effective_title != block_root.data.title:
                self.editor.edit_code_block(
                    block_id,
                    code=effective_code,
                    language="python",
                    title=effective_title,
                )

            effective_last_executed = last_executed
            if effective_last_executed is None:
                effective_last_executed = (
                    block_root.data.last_executed if is_executing else resolved_last_executed
                )

            updated_block = self.editor.update_code_block_execution(
                block_id,
                outputs=resolved_outputs,
                is_executing=is_executing,
                last_executed=effective_last_executed,
            )
            return updated_block

        block, actions, error = await self._handle_operation(
            f"Persisting Python execution state for block {block_id}",
            self.project_id,
            notebook_id,
            persist_operation,
            run_context=run_context,
        )

        if error or block is None:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=block_id,
                error=error or "Failed to persist Python execution state",
                message=f"Error persisting Python execution state for block {block_id} in notebook {notebook_id}",
            )

        return self._create_result(
            success=True,
            result_class=NotebookBlockResult,
            actions=actions,
            notebook_id=notebook_id,
            block_id=str(block.root.id),
            block=block,
            error=None,
            message=f"Successfully persisted Python execution state for block {block_id} in notebook {notebook_id}",
        )

    @updates_artifact(
        NotebookBlockResult,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Edit Python Block",
        emit_tool_call=True,
    )
    @validate_guids("notebook_id", "block_id")
    async def edit_python_code(
        self,
        block_id: str,
        code: str,
        notebook_id: str | None = None,
        title: str | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Edit an existing Python code block in the notebook.

        CRITICAL: If the code uses `kontext.load_data`, it MUST use `await`.
        Example: `df = await kontext.load_data('df_1')` — prefer the SQL block
        alias (also accepted: the block's durable `data_id`). Call
        `kontext.list_data_sources()` first to list loadable names instead of
        guessing (`{"aliases": [...], "data_ids": [...]}`).

        :param block_id: Block ID to edit.
        :param code: New Python code.
        :param notebook_id: Notebook ID. Optional: when omitted, defaults to the
            chat session's single linked notebook; pass it explicitly when more
            than one notebook is linked.
        :param title: Optional new title.
        :param run_context: runtime context.
        """
        notebook_id, _defaulted, resolution_error = await self._resolve_notebook_id(
            notebook_id, run_context
        )
        if resolution_error is not None:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id="",
                block_id=block_id,
                error=resolution_error,
                message=f"Error editing Python block {block_id}",
            )

        if not self.allow_python_blocks:
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=block_id,
                error="Python block mutation is not enabled in this notebook runtime.",
                message=f"Error editing Python block {block_id} in notebook {notebook_id}",
            )

        if not code or not code.strip():
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=block_id,
                error="Python code is required",
                message=f"Error editing Python block {block_id} in notebook {notebook_id}",
            )

        # Validate code before adding
        is_valid, issues = validate_python_code(code)
        if not is_valid:
            error_msg = f"Python code validation failed: {', '.join(issues)}"
            return self._create_result(
                success=False,
                result_class=NotebookBlockResult,
                notebook_id=notebook_id,
                block_id=block_id,
                error=error_msg,
                message=f"Error editing Python block {block_id} in notebook {notebook_id}",
            )

        async def edit_operation():
            self.logger.info(f"Editing Python block {block_id} in notebook: {notebook_id}")
            block_root = self._load_python_code_block(block_id)

            block_index = next(
                (
                    index
                    for index, notebook_block in enumerate(self.editor.get_notebook().blocks)
                    if str(notebook_block.root.id) == block_id
                ),
                None,
            )
            if block_index is None:
                raise ValueError(f"Block {block_id} not found in notebook state")
            effective_code, _inserted_count = await self._materialize_python_data_tables(
                code=code,
                run_context=run_context,
                insert_position=block_index,
            )
            self.editor.edit_code_block(
                block_id,
                code=effective_code,
                language="python",
                title=title if title is not None else block_root.data.title,
            )
            return self.editor.get_block(block_id)

        block, actions, error = await self._handle_operation(
            f"Editing Python block {block_id}",
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
                error=error or "Failed to edit Python block",
                message=f"Error editing Python block {block_id} in notebook {notebook_id}",
            )

        return self._create_result(
            success=True,
            result_class=NotebookBlockResult,
            actions=actions,
            notebook_id=notebook_id,
            block_id=str(block.root.id),
            error=None,
            message=f"Successfully edited Python block {block_id} in notebook {notebook_id}",
        )
