"""Python tools for validating and executing Python code in Kontext."""

import asyncio

from kontext.agent import RuntimeToolContext, ToolCallable
from kontext.agent.tools import ToolAction, tool_meta
from kontext.agentic.utils.guid_validation import validate_guids
from kontext.chat import execute_chat_session_python_script
from kontext.common.jobs.trigger_actor import agent_actor
from kontext.common.protocols import AIToolkitServiceProviderProtocol, IFileServiceProtocol
from kontext.common.python_execution.policy import WHITELISTED_MODULES, validate_python_code
from kontext.jobs import (
    NotebookPythonExecutionError,
    NotebookPythonExecutionService,
    PythonExecutionService,
)
from kontext.schema import (
    ArtifactOrigin,
    ArtifactProvenance,
    ArtifactType,
    CodeExecutionOutput,
    CodeTextOutput,
    ProjectModel,
    PythonExecutionMode,
    PythonExecutionResult,
    PythonExecutionTargetType,
    PythonValidationResult,
)

from .kontext_toolkit import KontextToolkit, ToolkitScope


class PythonExecutionMixin(KontextToolkit):
    """Notebook-Python execution surface shared by Python toolkits.

    Inherits the `KontextToolkit` service surface (`file_service`, `logger`,
    `project_id`, `chat_session_id`, `runtime_provider`,
    `list_artifact_descriptors`, `resolve_data_table_id`,
    `link_artifact_to_session`, `_wrap_result`) like `NotebookCoreMixin`
    does, so the host contract stays single-sourced instead of being
    re-declared per mixin.
    """

    # Attribution for execution jobs/provenance. NotebookPythonTools overrides this.
    python_execution_actor: str = "python_tool"

    # Set by ``_PythonToolkitBase.__init__`` on the concrete toolkits.
    file_service: IFileServiceProtocol | None
    python_execution_service: PythonExecutionService
    _editor_lock: asyncio.Lock

    def _build_python_error_result(
        self,
        *,
        message: str,
        error: str | None = None,
        outputs: list[CodeExecutionOutput] | None = None,
        notebook_id: str | None = None,
        execution_mode: PythonExecutionMode | None = None,
        execution_run_id: str | None = None,
        target_type: PythonExecutionTargetType | None = None,
    ) -> str:
        error_message = error or message
        result_outputs = list(outputs or [])
        if not result_outputs:
            result_outputs.append(
                CodeExecutionOutput(CodeTextOutput(mime_type="text/plain", content=error_message))
            )
        return self._wrap_result(
            PythonExecutionResult(
                success=False,
                message=message,
                error=error_message,
                outputs=result_outputs,
                notebook_id=notebook_id,
                execution_mode=execution_mode,
                execution_run_id=execution_run_id,
                target_type=target_type,
            )
        )

    async def _resolve_notebook_data_sources(
        self,
        run_context: RuntimeToolContext | None = None,
    ) -> dict[str, str]:
        scoped_sources: dict[str, str] = {}

        for descriptor in self.list_artifact_descriptors(
            run_context,
            artifact_type=ArtifactType.DATATABLE,
        ):
            primary_id = descriptor.artifact_id
            try:
                resolved_id = await self.resolve_data_table_id(
                    primary_id,
                    run_context=run_context,
                )
            except Exception as exc:
                self.logger.warning(
                    "Skipping unresolved Python shared data source %s: %s",
                    primary_id,
                    exc,
                )
                continue

            scoped_sources[str(primary_id)] = resolved_id

        return scoped_sources

    async def _resolve_execution_owner_id(self) -> str | None:
        """Resolve the chat session owner for execution attribution."""
        if not self.chat_session_id or self.runtime_provider is None:
            return None

        chat_session_service = self.runtime_provider.get_chat_session_service()
        if chat_session_service is None:
            return None

        try:
            chat_session = await chat_session_service.get_session(str(self.chat_session_id))
        except Exception as exc:
            self.logger.warning("Failed to resolve Python execution owner: %s", exc)
            return None

        owner_id = getattr(chat_session, "owner_id", None)
        return str(owner_id) if owner_id else None

    @tool_meta(
        PythonExecutionResult,
        action=ToolAction.UPDATE,
        artifact_type=ArtifactType.NOTEBOOK,
        display_name="Execute Python Code",
        emit_tool_call=True,
        emit_result=True,
        # Server tool bodies are never executed for ``external_execution`` tools:
        # the method exists only for schema/contract definition and validation
        # helpers. The client (HITL python flow) drives the actual execution.
        external_execution=True,
        strict=True,
        description=(
            "Required execution path for notebook Python blocks. Executing an existing block "
            "without a code override records its execution state on the notebook (outputs, "
            "lastExecuted); passing a code override runs a draft and leaves the notebook untouched."
        ),
    )
    @validate_guids("notebook_id", "block_id")
    async def execute_python_code(
        self,
        notebook_id: str,
        block_id: str,
        code: str | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Validate and execute Python code against an existing notebook block.

        :param notebook_id: Notebook ID.
        :param block_id: Existing notebook block ID to execute against.
        :param code: Optional code override; when provided, execution runs as a
            draft and the notebook is left untouched.
        :param run_context: runtime context.
        """
        if self.file_service is None:
            return self._build_python_error_result(
                message="Notebook file service is not available in this runtime.",
                notebook_id=notebook_id,
                execution_mode=PythonExecutionMode.DRAFT,
                target_type=PythonExecutionTargetType.NOTEBOOK,
            )

        if code is not None and not code.strip():
            return self._build_python_error_result(
                message="Python code cannot be empty when provided.",
                notebook_id=notebook_id,
                execution_mode=PythonExecutionMode.DRAFT,
                target_type=PythonExecutionTargetType.NOTEBOOK,
            )

        try:
            scoped_data_sources = await self._resolve_notebook_data_sources(run_context=run_context)
        except Exception as exc:
            return self._build_python_error_result(
                message="Failed to prepare scoped Python data sources.",
                error=str(exc),
                notebook_id=notebook_id,
                execution_mode=PythonExecutionMode.DRAFT,
                target_type=PythonExecutionTargetType.NOTEBOOK,
            )

        try:
            execution_service = NotebookPythonExecutionService(
                file_service=self.file_service,
                python_execution_service=self.python_execution_service,
                logger_=self.logger,
            )
            # Serialize with notebook block mutations: the execution service
            # loads and persists the same notebook document through the editor
            # path, so concurrent calls could lose an edit or execution state.
            async with self._editor_lock:
                python_result = await execution_service.execute_notebook_code_async(
                    project_id=self.project_id,
                    notebook_id=notebook_id,
                    block_id=block_id,
                    chat_session_id=self.chat_session_id,
                    code_override=code,
                    persist_notebook_state=code is None,
                    data_sources=scoped_data_sources,
                    owner_id=await self._resolve_execution_owner_id(),
                    triggered_by=agent_actor(self.python_execution_actor),
                )
            if run_context:
                await self.link_artifact_to_session(
                    artifact_id=notebook_id,
                    artifact_type=ArtifactType.NOTEBOOK,
                    run_context=run_context,
                )
        except NotebookPythonExecutionError as exc:
            result = exc.to_result(
                notebook_id=notebook_id,
                execution_mode=PythonExecutionMode.DRAFT,
                execution_run_id=None,
            )
            result.target_type = PythonExecutionTargetType.NOTEBOOK
            return self._wrap_result(result)

        python_result.target_type = PythonExecutionTargetType.NOTEBOOK
        await self._register_saved_tables(python_result, run_context)
        if code is None:
            self.logger.info(
                "Python tool executed notebook block for notebook=%s block=%s run=%s; "
                "execution state recorded on the notebook.",
                notebook_id,
                block_id,
                python_result.execution_run_id,
            )
        else:
            self.logger.info(
                "Python tool executed draft notebook code for notebook=%s block=%s run=%s; "
                "notebook left untouched.",
                notebook_id,
                block_id,
                python_result.execution_run_id,
            )
        return self._wrap_result(python_result)

    async def _register_saved_tables(
        self,
        python_result: PythonExecutionResult,
        run_context: RuntimeToolContext | None,
    ) -> None:
        """Share ``kontext.save_table`` outputs with the rest of the team.

        Durable ids already resolve on their own; the descriptor adds the
        title/row count so other agents can see what the table is. The HITL
        path performs the same registration on resume (server tool bodies are
        not executed for external-execution tools).
        """
        for saved in python_result.saved_tables or []:
            try:
                await self.link_artifact_to_session(
                    artifact_id=saved.data_table_id,
                    artifact_type=ArtifactType.DATATABLE,
                    title=saved.title,
                    row_count=saved.row_count,
                    run_context=run_context,
                )
            except Exception as exc:
                self.logger.warning(
                    "Could not register saved table %s in shared session state: %s",
                    saved.data_table_id,
                    exc,
                )


class _PythonToolkitBase(PythonExecutionMixin):
    """Shared construction for toolkits that execute managed Python.

    Keeps the service wiring and the execution mixin contract in one place;
    concrete toolkits only choose their name and exposed tool surface.
    """

    def __init__(
        self,
        *,
        name: str,
        tools: list[ToolCallable],
        project: ProjectModel | None = None,
        runtime_provider: AIToolkitServiceProviderProtocol | None = None,
        session_id: str | None = None,
        chat_session_id: str | None = None,
        catalog_connection_id: str | None = None,
        default_namespace: str | None = None,
        default_entity_id: str | None = None,
        engine_type: str | None = None,
        scope: ToolkitScope | None = None,
        editor_lock: asyncio.Lock | None = None,
    ) -> None:
        super().__init__(
            name=name,
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
        self.python_execution_service = PythonExecutionService()
        self._editor_lock = editor_lock or asyncio.Lock()


class PythonTools(_PythonToolkitBase):
    """Toolkit for Python code generation guidance, validation, and execution."""

    def __init__(
        self,
        project: ProjectModel | None = None,
        runtime_provider: AIToolkitServiceProviderProtocol | None = None,
        session_id: str | None = None,
        chat_session_id: str | None = None,
        catalog_connection_id: str | None = None,
        default_namespace: str | None = None,
        default_entity_id: str | None = None,
        engine_type: str | None = None,
        scope: ToolkitScope | None = None,
        include_notebook_execution: bool = True,
        editor_lock: asyncio.Lock | None = None,
    ) -> None:
        """
        Initialize Python tools with service factories.

        Args:
            project: Project model with full context
            session_id: Optional ID of the query session
            chat_session_id: Optional ID of the chat session
            engine_type: Optional default engine type
            include_notebook_execution: Expose notebook-block execution. Disable
                for the standalone Python agent so the Notebook agent remains the
                single owner of notebook Python execution.
            editor_lock: Optional lock shared with a notebook toolkit so block
                mutation and execution cannot race.
        """
        tools = [
            self.validate_python_code,
            self.execute_python_script,
            self.get_allowed_libraries,
        ]
        if include_notebook_execution:
            tools.insert(1, self.execute_python_code)

        super().__init__(
            name="PythonTools",
            tools=tools,
            project=project,
            runtime_provider=runtime_provider,
            session_id=session_id,
            chat_session_id=chat_session_id,
            catalog_connection_id=catalog_connection_id,
            default_namespace=default_namespace,
            default_entity_id=default_entity_id,
            engine_type=engine_type,
            scope=scope,
            editor_lock=editor_lock,
        )

    @tool_meta(PythonValidationResult, display_name="Validate Code", emit_tool_call=True)
    async def validate_python_code(self, code: str) -> str:
        """Validate Python code for security and syntax.

        :param code: Python code to validate.
        """
        try:
            self.logger.info(f"Validating Python code for project {self.project_id}")

            is_valid, issues = validate_python_code(code)

            return self._create_result(
                success=True,
                result_class=PythonValidationResult,
                valid=is_valid,
                issues=issues,
                message=(
                    "Code validation completed successfully"
                    if is_valid
                    else "Code validation found issues"
                ),
            )
        except Exception as e:
            self.logger.error(f"Error validating Python code: {e}")
            return self._create_result(
                success=False,
                result_class=PythonValidationResult,
                valid=False,
                issues=[str(e)],
                message="Failed to validate Python code",
            )

    @tool_meta(
        PythonExecutionResult,
        display_name="Execute Python Script",
        emit_tool_call=True,
        emit_result=True,
        # Server tool bodies are never executed for ``external_execution`` tools:
        # the method exists only for schema/contract definition and validation
        # helpers. The client (HITL python flow) drives the actual execution.
        external_execution=True,
        strict=True,
        description=(
            "Execute session-scoped managed Python for non-notebook tasks only. Session runs can access all "
            "current data-table artifacts linked to the active chat session. Session-scoped scripts may use "
            "`await kontext.execute_sql(...)` for transient read-only SQL within the active chat query context."
        ),
    )
    async def execute_python_script(
        self,
        code: str,
        run_context: RuntimeToolContext | None = None,
    ) -> str:
        """Validate and execute session-scoped Python code."""
        if not code.strip():
            return self._build_python_error_result(
                message="Python code cannot be empty.",
                target_type=PythonExecutionTargetType.SESSION,
            )

        if not self.chat_session_id:
            return self._build_python_error_result(
                message=(
                    "Session-scoped Python execution requires an active chat session "
                    "so chat-session data tables and query context can be resolved."
                ),
                target_type=PythonExecutionTargetType.SESSION,
            )

        chat_session_service = (
            self.runtime_provider.get_chat_session_service()
            if self.runtime_provider is not None
            else None
        )
        if chat_session_service is None:
            return self._build_python_error_result(
                message=(
                    "Chat session service is not available, so session-scoped Python "
                    "execution cannot resolve chat-session data tables or query context."
                ),
                target_type=PythonExecutionTargetType.SESSION,
            )

        try:
            execution_result = await execute_chat_session_python_script(
                project_id=self.project_id,
                chat_session_id=self.chat_session_id,
                code=code,
                chat_session_service=chat_session_service,
                python_execution_service=self.python_execution_service,
                triggered_by=agent_actor("python_tool"),
            )
        except Exception as exc:
            return self._build_python_error_result(
                message="Managed Python execution failed before returning a result.",
                error=str(exc),
                target_type=PythonExecutionTargetType.SESSION,
            )

        python_result = execution_result.python_result
        python_result.target_type = PythonExecutionTargetType.SESSION
        python_result.provenance = ArtifactProvenance(
            origin=ArtifactOrigin.AGENTPYTHON,
            created_by=agent_actor("python_tool"),
            execution_run_id=python_result.execution_run_id,
            chat_session_id=str(self.chat_session_id),
        )
        # The execution bridge already linked ``kontext.save_table`` outputs to
        # the chat session's artifact panel; register them in shared session
        # state here (only the tool can reach it for server-side calls).
        await self._register_saved_tables(python_result, run_context)
        return self._wrap_result(python_result)

    @tool_meta(display_name="Get Allowed Libraries", emit_tool_call=False)
    async def get_allowed_libraries(self) -> str:
        """List allowed Python libraries."""
        return ", ".join(sorted(WHITELISTED_MODULES))


class NotebookPythonTools(_PythonToolkitBase):
    """Notebook-owned Python execution toolkit.

    Exposes only block execution, so the Notebook agent can run the blocks it
    owns without gaining the standalone agent's session-scoped execution or the
    Notebook structure/editor tools. Attribution is recorded as
    ``notebook_tool`` rather than ``python_tool``.
    """

    python_execution_actor = "notebook_tool"

    def __init__(
        self,
        project: ProjectModel | None = None,
        runtime_provider: AIToolkitServiceProviderProtocol | None = None,
        session_id: str | None = None,
        chat_session_id: str | None = None,
        catalog_connection_id: str | None = None,
        default_namespace: str | None = None,
        default_entity_id: str | None = None,
        engine_type: str | None = None,
        scope: ToolkitScope | None = None,
        editor_lock: asyncio.Lock | None = None,
    ) -> None:
        super().__init__(
            name="NotebookPythonTools",
            tools=[self.execute_python_code],
            project=project,
            runtime_provider=runtime_provider,
            session_id=session_id,
            chat_session_id=chat_session_id,
            catalog_connection_id=catalog_connection_id,
            default_namespace=default_namespace,
            default_entity_id=default_entity_id,
            engine_type=engine_type,
            scope=scope,
            editor_lock=editor_lock,
        )
