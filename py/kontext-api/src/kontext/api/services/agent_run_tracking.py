"""Execution-run tracking for chat streaming workflows.

Single seam between kontext-chat's ``ChatExecutionTrackerProtocol`` and the
execution lifecycle. Lives apart from both chats and execution_runs so the
modules cannot import each other: ``execution_runs`` (the /runs transport
adapter) may read from chats; chats reads only from here.
"""

from __future__ import annotations

from uuid import UUID

from kontext.chat import ChatExecutionTrackerProtocol
from kontext.execution.lifecycle import ExecutionLifecycleService
from kontext.schema import (
    ExecutionRunModel,
    SimpleRunEvent,
    TriggerActorModel,
)

#: Stateless lifecycle service shared by all in-process tracking paths.
LIFECYCLE_SERVICE = ExecutionLifecycleService()


async def create_agent_execution_run_async(
    *,
    project_id: UUID,
    owner_id: UUID,
    chat_session_id: UUID,
    triggered_by: TriggerActorModel | None,
    engine_type: str | None = None,
) -> ExecutionRunModel:
    return await LIFECYCLE_SERVICE.create_agent_execution_run_async(
        project_id=project_id,
        owner_id=owner_id,
        chat_session_id=chat_session_id,
        triggered_by=triggered_by,
        engine_type=engine_type,
    )


async def mark_agent_execution_running_async(
    *,
    project_id: UUID,
    platform_run_id: UUID,
    chat_session_id: UUID,
    agent_runtime_run_id: str | None = None,
    message: str = "Agent execution running",
) -> None:
    await LIFECYCLE_SERVICE.mark_agent_execution_running_async(
        project_id=project_id,
        platform_run_id=platform_run_id,
        chat_session_id=chat_session_id,
        agent_runtime_run_id=agent_runtime_run_id,
        message=message,
    )


async def resolve_waiting_agent_execution_run_id_async(
    *,
    project_id: UUID,
    chat_session_id: UUID,
    agent_runtime_run_id: str | None = None,
) -> UUID | None:
    return await LIFECYCLE_SERVICE.resolve_waiting_agent_execution_run_id_async(
        project_id=project_id,
        chat_session_id=chat_session_id,
        agent_runtime_run_id=agent_runtime_run_id,
    )


async def persist_agent_execution_event_async(
    *,
    project_id: UUID,
    platform_run_id: UUID,
    chat_session_id: UUID,
    event: SimpleRunEvent,
) -> SimpleRunEvent:
    return await LIFECYCLE_SERVICE.persist_agent_execution_event_async(
        project_id=project_id,
        platform_run_id=platform_run_id,
        chat_session_id=chat_session_id,
        event=event,
    )


class ExecutionRunTracker(ChatExecutionTrackerProtocol):
    """Chat-facing adapter over the lifecycle tracking wrappers."""

    async def resolve_waiting_run_id(
        self,
        *,
        project_id: UUID,
        chat_session_id: UUID,
        agent_runtime_run_id: str | None = None,
    ) -> UUID | None:
        return await resolve_waiting_agent_execution_run_id_async(
            project_id=project_id,
            chat_session_id=chat_session_id,
            agent_runtime_run_id=agent_runtime_run_id,
        )

    async def create_run(
        self,
        *,
        project_id: UUID,
        owner_id: UUID,
        chat_session_id: UUID,
        triggered_by: TriggerActorModel | None,
        engine_type: str | None = None,
    ) -> UUID:
        run = await create_agent_execution_run_async(
            project_id=project_id,
            owner_id=owner_id,
            chat_session_id=chat_session_id,
            triggered_by=triggered_by,
            engine_type=engine_type,
        )
        return UUID(str(run.id))

    async def mark_run_running(
        self,
        *,
        project_id: UUID,
        platform_run_id: UUID,
        chat_session_id: UUID,
        agent_runtime_run_id: str | None = None,
        message: str = "Agent execution running",
    ) -> None:
        await mark_agent_execution_running_async(
            project_id=project_id,
            platform_run_id=platform_run_id,
            chat_session_id=chat_session_id,
            agent_runtime_run_id=agent_runtime_run_id,
            message=message,
        )

    async def persist_event(
        self,
        *,
        project_id: UUID,
        platform_run_id: UUID,
        chat_session_id: UUID,
        event: SimpleRunEvent,
    ) -> SimpleRunEvent:
        return await persist_agent_execution_event_async(
            project_id=project_id,
            platform_run_id=platform_run_id,
            chat_session_id=chat_session_id,
            event=event,
        )


EXECUTION_RUN_TRACKER = ExecutionRunTracker()
