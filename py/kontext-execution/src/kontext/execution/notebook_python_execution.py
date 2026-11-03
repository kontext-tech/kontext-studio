"""Shared notebook Python execution orchestration built on managed CPython."""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

from kontext.common.notebook_aliases import normalize_sql_aliases
from kontext.common.protocols import IFileServiceProtocol
from kontext.common.python_execution.helpers import extract_kontext_load_data_ids
from kontext.common.python_execution.policy import validate_python_code
from kontext.schema import (
    ArtifactAction,
    ArtifactOrigin,
    ArtifactProvenance,
    CodeBlock,
    CodeExecutionOutput,
    CodeTextOutput,
    NotebookBlock,
    NotebookDocument,
    NotebookUpsertBlockAction,
    NotebookUpsertBlockActionPayload,
    PythonExecutionMode,
    PythonExecutionResult,
    PythonExecutionTargetType,
    SqlBlock,
    TriggerActorModel,
)

from .python_execution import PythonExecutionService

logger = logging.getLogger(__name__)


class NotebookPythonExecutionError(RuntimeError):
    """Raised when notebook Python execution cannot be prepared or persisted."""

    def __init__(
        self,
        message: str,
        *,
        error: str | None = None,
        status_code: int = 400,
        outputs: list[CodeExecutionOutput] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error = error or message
        self.status_code = status_code
        self.outputs = outputs or []

    def to_result(
        self,
        *,
        notebook_id: str | None = None,
        execution_mode: PythonExecutionMode | None = None,
        execution_run_id: str | None = None,
    ) -> PythonExecutionResult:
        outputs = list(self.outputs)
        if not outputs:
            outputs.append(
                CodeExecutionOutput(CodeTextOutput(mime_type="text/plain", content=self.error))
            )
        return PythonExecutionResult(
            success=False,
            message=self.message,
            error=self.error,
            outputs=outputs,
            notebook_id=notebook_id,
            execution_mode=execution_mode,
            execution_run_id=execution_run_id,
        )


class NotebookPythonExecutionService:
    """Coordinate notebook block persistence around managed Python execution."""

    def __init__(
        self,
        *,
        file_service: IFileServiceProtocol,
        python_execution_service: PythonExecutionService | None = None,
        logger_: logging.Logger | None = None,
    ) -> None:
        self.file_service = file_service
        self.python_execution_service = python_execution_service or PythonExecutionService()
        self.logger = logger_ or logger
        self._next_sequence = int(time.time() * 1_000_000)

    async def execute_notebook_code_async(
        self,
        *,
        project_id: str,
        notebook_id: str,
        block_id: str,
        data_sources: dict[str, str] | None = None,
        chat_session_id: str | None = None,
        code_override: str | None = None,
        persist_notebook_state: bool = True,
        owner_id: UUID | str | None = None,
        triggered_by: TriggerActorModel | None = None,
        run_id: UUID | str | None = None,
    ) -> PythonExecutionResult:
        execution_mode = (
            PythonExecutionMode.PERSISTED if persist_notebook_state else PythonExecutionMode.DRAFT
        )
        notebook = await self._load_notebook(project_id, notebook_id)
        # Bind notebook-scoped aliases server-side (df_N) before validation
        # and scoping: client-stamped results may reach the document through
        # raw JSON saves that bypass the editor, so the python block's own
        # execution is also a binding moment (the follow-up execution-state
        # persist writes the assignment back).
        normalize_sql_aliases(notebook)
        block, _block_index = self._get_python_block(notebook, notebook_id, block_id)
        effective_code = code_override if code_override is not None else block.data.code
        self._validate_python_code(effective_code)
        self._validate_notebook_data_references(notebook, effective_code)
        scoped_data_sources = self._build_scoped_data_sources(notebook, data_sources)

        pre_actions: list[ArtifactAction] = []
        if persist_notebook_state:
            pre_actions = await self._persist_execution_state(
                project_id=project_id,
                notebook_id=notebook_id,
                block_id=block_id,
                outputs=None,
                is_executing=True,
            )

        execution_run_id: str | None = None
        try:
            execution_result = await self.python_execution_service.execute_notebook_code_async(
                project_id=project_id,
                notebook_id=notebook_id,
                block_id=block_id,
                chat_session_id=chat_session_id,
                code=effective_code,
                data_sources=scoped_data_sources,
                owner_id=owner_id,
                triggered_by=triggered_by,
                run_id=run_id,
            )
            execution_run_id = execution_result.execution_run.id
            python_result = execution_result.python_result.model_copy(deep=True)
            self.logger.info(
                ("Notebook Python execution completed for notebook=%s block=%s run=%s mode=%s"),
                notebook_id,
                block_id,
                execution_run_id,
                execution_mode,
            )
        except Exception as exc:
            self.logger.exception(
                "Managed notebook Python execution failed before returning a result"
            )
            python_result = PythonExecutionResult(
                success=False,
                message=("Python execution failed before the managed runner returned a result."),
                error=str(exc),
                outputs=[
                    CodeExecutionOutput(CodeTextOutput(mime_type="text/plain", content=str(exc)))
                ],
                execution_mode=execution_mode,
            )

        post_actions: list[ArtifactAction] = []
        last_executed = int(time.time() * 1000)
        if persist_notebook_state:
            try:
                post_actions = await self._persist_execution_state(
                    project_id=project_id,
                    notebook_id=notebook_id,
                    block_id=block_id,
                    outputs=python_result.outputs,
                    is_executing=False,
                    last_executed=last_executed,
                )
            except NotebookPythonExecutionError as exc:
                message = "Python code executed but notebook outputs could not be persisted."
                raise NotebookPythonExecutionError(
                    message,
                    error=exc.error,
                    status_code=exc.status_code,
                    outputs=python_result.outputs,
                ) from exc
        else:
            post_actions = [
                self._build_execution_state_action(
                    block_id=block_id,
                    block_index=_block_index,
                    block=self._build_updated_execution_block(
                        block,
                        outputs=python_result.outputs,
                        is_executing=False,
                        last_executed=last_executed,
                        code=effective_code if code_override is not None else None,
                    ),
                )
            ]

        python_result.notebook_id = notebook_id
        # ``execution_run_id`` is already stamped on the envelope from the job
        # run (see PythonExecutionService); assignments here would be redundant.
        python_result.execution_mode = execution_mode
        python_result.target_type = PythonExecutionTargetType.NOTEBOOK
        python_result.actions = [*pre_actions, *post_actions]
        python_result.provenance = ArtifactProvenance(
            origin=ArtifactOrigin.NOTEBOOKRUN,
            created_by=triggered_by,
            execution_run_id=execution_run_id,
            chat_session_id=chat_session_id,
            block_id=block_id,
        )
        if execution_mode == PythonExecutionMode.DRAFT:
            self.logger.info(
                (
                    "Notebook Python draft execution produced transient "
                    "outputs for notebook=%s block=%s run=%s"
                ),
                notebook_id,
                block_id,
                execution_run_id,
            )
        return python_result

    async def _load_notebook(
        self,
        project_id: str,
        notebook_id: str,
    ) -> NotebookDocument:
        try:
            content = await self.file_service.get_file_content(project_id, notebook_id)
            return NotebookDocument.model_validate_json(content)
        except Exception as exc:
            detail = str(exc)
            status_code = 404 if "not found" in detail.lower() else 500
            raise NotebookPythonExecutionError(
                f"Failed to load notebook {notebook_id} for Python execution.",
                error=detail,
                status_code=status_code,
            ) from exc

    def _get_python_block(
        self,
        notebook: NotebookDocument,
        notebook_id: str,
        block_id: str,
    ) -> tuple[CodeBlock, int]:
        for index, wrapped_block in enumerate(notebook.blocks):
            block = wrapped_block.root
            if str(block.id) != block_id:
                continue
            if not isinstance(block, CodeBlock):
                raise NotebookPythonExecutionError(
                    f"Block {block_id} is not a code block.",
                    status_code=400,
                )
            if block.data.language.lower() != "python":
                raise NotebookPythonExecutionError(
                    f"Block {block_id} is a {block.data.language} block, not Python.",
                    status_code=400,
                )
            return block, index

        raise NotebookPythonExecutionError(
            f"Code block {block_id} was not found in notebook {notebook_id}.",
            status_code=404,
        )

    def _validate_python_code(self, code: str) -> None:
        """Pre-dispatch security filter for interactive notebook execution.

        The alias "add the import" guidance is *not* applied here: whether an
        alias may already be persisted depends on the session kernel, which the
        dispatcher owns and re-validates with that knowledge (``shared_namespace``).
        """
        is_valid, issues = validate_python_code(code, shared_namespace=True)
        if not is_valid:
            raise NotebookPythonExecutionError(
                "Python code validation failed.",
                error=", ".join(issues),
                status_code=400,
            )

    def _validate_notebook_data_references(
        self,
        notebook: NotebookDocument,
        code: str,
    ) -> None:
        referenced_data_ids = set(extract_kontext_load_data_ids(code))
        if not referenced_data_ids:
            return

        notebook_sql_data_ids = self._collect_notebook_sql_data_ids(notebook)
        notebook_aliases = self._collect_notebook_sql_aliases(notebook)
        missing_data_ids = sorted(
            referenced_data_ids.difference(notebook_sql_data_ids, set(notebook_aliases))
        )
        if not missing_data_ids:
            return

        missing_list = ", ".join(missing_data_ids)
        raise NotebookPythonExecutionError(
            "Notebook Python execution requires every referenced data ID to be "
            "materialized in the notebook.",
            error=(
                "Add or import notebook data table blocks for these data IDs "
                "before running the Python block: "
                f"{missing_list}. Available block aliases: {sorted(notebook_aliases)}"
            ),
            status_code=400,
        )

    def _build_scoped_data_sources(
        self,
        notebook: NotebookDocument,
        provided_sources: dict[str, str] | None,
    ) -> dict[str, str]:
        scoped_sources = dict(provided_sources or {})
        for data_id in self._collect_notebook_data_ids(notebook):
            scoped_sources.setdefault(data_id, data_id)
        # Notebook-scope aliases (df_N / renames on SQL blocks) load the same
        # result table by name; UUID keys keep working unchanged.
        for alias, data_id in self._collect_notebook_sql_aliases(notebook).items():
            scoped_sources.setdefault(alias, data_id)
        return scoped_sources

    def _collect_notebook_sql_aliases(self, notebook: NotebookDocument) -> dict[str, str]:
        """Map each unambiguous SQL block alias to its result data ID.

        Blocks without persisted results have nothing to bind, so their alias
        is not loadable. An alias pointing at conflicting tables (corrupt or
        hand-edited docs) is dropped with a warning instead of resolving
        nondeterministically.
        """
        aliases: dict[str, str] = {}
        ambiguous: set[str] = set()
        for block in notebook.blocks:
            root = block.root
            if not isinstance(root, SqlBlock):
                continue
            alias = root.data.alias
            data_id = getattr(root.data.data_ref, "data_id", None) if root.data.data_ref else None
            if not alias or not data_id:
                continue
            alias = str(alias)
            if alias in ambiguous:
                continue
            previous = aliases.get(alias)
            if previous is not None and previous != str(data_id):
                del aliases[alias]
                ambiguous.add(alias)
                self.logger.warning(
                    "Ignoring ambiguous notebook data alias %s (blocks disagree: %s vs %s)",
                    alias,
                    previous,
                    data_id,
                )
                continue
            aliases[alias] = str(data_id)
        return aliases

    def _collect_notebook_data_ids(self, notebook: NotebookDocument) -> set[str]:
        data_ids: set[str] = set()
        for block in notebook.blocks:
            data_ref = getattr(getattr(block.root, "data", None), "data_ref", None)
            data_id = getattr(data_ref, "data_id", None)
            if data_id:
                data_ids.add(str(data_id))
        return data_ids

    def _collect_notebook_sql_data_ids(self, notebook: NotebookDocument) -> set[str]:
        data_ids: set[str] = set()
        for block in notebook.blocks:
            root = block.root
            if not isinstance(root, SqlBlock):
                continue
            data_ref = getattr(root.data, "data_ref", None)
            data_id = getattr(data_ref, "data_id", None)
            if data_id:
                data_ids.add(str(data_id))
        return data_ids

    async def _persist_execution_state(
        self,
        *,
        project_id: str,
        notebook_id: str,
        block_id: str,
        outputs: list[CodeExecutionOutput] | None,
        is_executing: bool,
        last_executed: int | None = None,
    ) -> list[ArtifactAction]:
        notebook = await self._load_notebook(project_id, notebook_id)
        # Re-bind aliases on the freshly loaded doc so the persist writes
        # user names and df_N bindings back alongside execution state.
        normalize_sql_aliases(notebook)
        block, block_index = self._get_python_block(notebook, notebook_id, block_id)

        updated_block = self._build_updated_execution_block(
            block,
            outputs=outputs,
            is_executing=is_executing,
            last_executed=last_executed,
        )
        notebook.blocks[block_index] = NotebookBlock(updated_block)
        notebook.modified = int(time.time() * 1000)

        try:
            await self.file_service.update_notebook(
                project_id=project_id,
                file_id=notebook_id,
                notebook=notebook,
            )
        except Exception as exc:
            detail = str(exc)
            raise NotebookPythonExecutionError(
                f"Failed to persist execution state for block {block_id}.",
                error=detail,
                status_code=500,
            ) from exc

        return [
            self._build_execution_state_action(
                block_id=block_id,
                block_index=block_index,
                block=updated_block,
            )
        ]

    def _build_updated_execution_block(
        self,
        block: CodeBlock,
        *,
        outputs: list[CodeExecutionOutput] | None,
        is_executing: bool,
        last_executed: int | None = None,
        code: str | None = None,
    ) -> CodeBlock:
        updated_data = block.data.model_copy(deep=True)
        updated_data.outputs = outputs
        updated_data.is_executing = is_executing
        if last_executed is not None:
            updated_data.last_executed = last_executed
        if code is not None:
            updated_data.code = code

        updated_block = block.model_copy(deep=True)
        updated_block.data = updated_data
        return updated_block

    def _build_execution_state_action(
        self,
        *,
        block_id: str,
        block_index: int,
        block: CodeBlock,
    ) -> ArtifactAction:
        return ArtifactAction(
            root=NotebookUpsertBlockAction(
                sequence=self._next_action_sequence(),
                action_type="upsertBlock",
                payload=NotebookUpsertBlockActionPayload(
                    cid=block_id,
                    block_type=self._block_type_value(block.type),
                    data=block.data.model_dump(
                        by_alias=True,
                        exclude_none=True,
                    ),
                    position=block_index,
                ),
            )
        )

    def _next_action_sequence(self) -> int:
        current_time_seq = int(time.time() * 1_000_000)
        self._next_sequence = max(self._next_sequence + 1, current_time_seq)
        return self._next_sequence

    @staticmethod
    def _block_type_value(block_type: Any) -> str:
        return block_type.value if hasattr(block_type, "value") else str(block_type)
