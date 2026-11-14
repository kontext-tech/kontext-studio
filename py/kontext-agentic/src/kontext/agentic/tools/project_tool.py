"""Project tools for retrieving project information from Kontext."""

import json
from uuid import UUID

from kontext.agent.tools import tool_meta
from kontext.common.protocols import AIToolkitServiceProviderProtocol
from kontext.file.notebook.editor import NotebookEditor
from kontext.jobs import ExecutionRunService
from kontext.schema import CodeBlock, ProjectModel, ProjectResult

from ..utils.guid_validation import validate_guid, validate_guids
from .kontext_toolkit import KontextToolkit, ToolkitScope


class ProjectTools(KontextToolkit):
    """Toolkit for retrieving project details by project ID."""

    def __init__(
        self,
        project: ProjectModel | None = None,
        runtime_provider: AIToolkitServiceProviderProtocol | None = None,
        scope: ToolkitScope | None = None,
    ) -> None:
        """Initialize the project toolkit."""
        super().__init__(
            name="ProjectTools",
            project=project,
            runtime_provider=runtime_provider,
            scope=scope,
            tools=[
                self.get_project,
                self.inspect_notebook_python_state,
                self.inspect_notebooks_python_state,
            ],
        )
        self.project_service = self.get_project_service()

    @tool_meta(ProjectResult)
    async def get_project(self) -> str:
        """Get project by ID.

        :return: JSON with project data
        """
        try:
            self.logger.info(f"Retrieving project: {self.project_id}")

            # Get project by ID
            if self.project_service:
                project = await self.project_service.get_project_async()
            else:
                project = self.project

            if not project:
                return self._wrap_result(
                    ProjectResult(
                        success=False, project=None, message=f"Project {self.project_id} not found"
                    )
                )

            result = ProjectResult(
                success=True,
                project=project,
                message=f"Successfully retrieved project '{project.project_name}' (code: {project.project_code})",
            )

            self.logger.info(f"Successfully retrieved project {self.project_id}")
            return self._wrap_result(result)

        except Exception as e:
            error_msg = f"Failed to retrieve project: {e!s}"
            self.logger.error(error_msg, exc_info=True)

            error_result = ProjectResult(
                success=False, project=None, message=f"Error retrieving project: {error_msg}"
            )
            return self._wrap_result(error_result)

    @tool_meta(display_name="Inspect Notebook Python State", emit_tool_call=True)
    @validate_guids("notebook_id")
    async def inspect_notebook_python_state(self, notebook_id: str) -> str:
        """Inspect the execution state of Python blocks in a notebook (read-only).

        :param notebook_id: Notebook ID.
        """
        payload = await self._inspect_one_notebook_python_state(notebook_id)
        return json.dumps(payload, ensure_ascii=True)

    @tool_meta(display_name="Inspect Notebooks Python State (Batch)", emit_tool_call=True)
    async def inspect_notebooks_python_state(self, notebook_ids: list[str]) -> str:
        """Inspect Python-block execution state across several notebooks in one call.

        :param notebook_ids: Notebook IDs to inspect.
        """
        payloads: list[dict[str, object]] = []
        for notebook_id in notebook_ids:
            try:
                validate_guid(notebook_id, "notebook_id")
            except ValueError as exc:
                payloads.append({"success": False, "notebookId": notebook_id, "error": str(exc)})
                continue
            payloads.append(await self._inspect_one_notebook_python_state(notebook_id))

        failed_count = sum(1 for payload in payloads if payload.get("success") is False)
        return json.dumps(
            {
                "success": bool(payloads) and failed_count == 0,
                "message": (f"Inspected {len(payloads)} notebook(s); {failed_count} failed."),
                "notebooksCount": len(payloads),
                "failedCount": failed_count,
                "notebooks": payloads,
            },
            ensure_ascii=True,
        )

    async def _inspect_one_notebook_python_state(self, notebook_id: str) -> dict[str, object]:
        """Build the read-only Python-block state payload for one notebook."""
        payload: dict[str, object] = {"success": False, "notebookId": notebook_id}
        file_service = self.get_file_service()
        if file_service is None:
            payload["error"] = "Notebook file service is not available in this runtime."
            return payload

        try:
            editor = NotebookEditor(
                file_service=file_service,
                logger=self.logger,
                project_id=self.project_id,
            )
            await editor.load_notebook_from_file(self.project_id, notebook_id)
            notebook = editor.get_notebook()
        except Exception as exc:
            payload["error"] = f"Failed to load notebook {notebook_id}: {exc!s}"
            self.logger.error(payload["error"], exc_info=True)
            return payload

        python_blocks: list[dict[str, object]] = []
        recent_runs_by_block: dict[str, dict[str, object]] = {}
        recent_runs_error: str | None = None
        try:
            recent_runs = await ExecutionRunService().list_recent_notebook_python_runs_async(
                project_id=UUID(str(self.project_id)),
                notebook_id=notebook_id,
                limit=10,
            )
            # Most recent first: keep the first (newest) run per block, which
            # also preserves newest-first order across blocks.
            for run in recent_runs:
                recent_runs_by_block.setdefault(str(run.get("blockId") or ""), run)
        except Exception as exc:
            recent_runs_error = str(exc)
            self.logger.warning(
                "Failed to list recent notebook Python runs for notebook %s: %s",
                notebook_id,
                exc,
            )

        for notebook_block in notebook.blocks:
            block_root = notebook_block.root
            if not isinstance(block_root, CodeBlock):
                continue
            block_language = getattr(block_root.data.language, "value", block_root.data.language)
            if str(block_language).lower() != "python":
                continue

            block_id = str(block_root.id)
            outputs = block_root.data.outputs or []
            is_executing = bool(block_root.data.is_executing)
            last_executed = block_root.data.last_executed
            state = "executing" if is_executing else "executed" if last_executed else "unexecuted"
            recent_run = recent_runs_by_block.get(block_id)
            python_blocks.append(
                {
                    "blockId": block_id,
                    "title": block_root.data.title,
                    "executionState": state,
                    "isExecuting": is_executing,
                    "outputCount": len(outputs),
                    "lastExecuted": last_executed,
                    "recentRunId": (recent_run or {}).get("runId"),
                }
            )

        unexecuted = [
            block["blockId"] for block in python_blocks if block["executionState"] == "unexecuted"
        ]
        ordered_recent_runs = list(recent_runs_by_block.values())
        payload.update(
            {
                "success": True,
                "pythonBlocks": python_blocks,
                "recentExecutionRuns": ordered_recent_runs,
                "hasUnexecutedBlocks": bool(unexecuted),
                "unexecutedBlockIds": unexecuted,
                "message": (
                    f"Notebook {notebook_id} has {len(unexecuted)} unexecuted Python block(s)."
                    if unexecuted
                    else f"All {len(python_blocks)} Python block(s) in notebook {notebook_id} carry execution state."
                ),
            }
        )
        if recent_runs_error is not None:
            payload["recentExecutionRunsError"] = recent_runs_error
        latest_recent_run = next(iter(recent_runs_by_block.values()), None)
        if unexecuted and latest_recent_run and str(latest_recent_run.get("runId") or ""):
            payload["persistHint"] = (
                "A recent managed run exists for this notebook; attach it to a block with "
                "`persist_python_execution_state(notebook_id, block_id, execution_run_id)` "
                "using the `runId`/`recentRunId` recorded above."
            )
        return payload
