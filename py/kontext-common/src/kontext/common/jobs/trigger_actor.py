"""Builders for structured job trigger actor references.

A job trigger records *who or what* caused a job to run. Instead of encoding
that in a free-form string, producers build a :class:`TriggerActorModel` with a
:class:`TriggerActorType` and an optional artifact id, so consumers can render a
label and link to the referenced artifact.
"""

from __future__ import annotations

from kontext.schema import TriggerActorModel, TriggerActorType


def user_actor(user_id: str) -> TriggerActorModel:
    """Actor for a human user identified by their user id."""
    return TriggerActorModel(type=TriggerActorType.USER, id=str(user_id))


def agent_actor(name: str | None = None) -> TriggerActorModel:
    """Actor for an AI agent or agent tool (optionally named)."""
    return TriggerActorModel(type=TriggerActorType.AGENT, id=name)


def notebook_actor(notebook_id: str) -> TriggerActorModel:
    """Actor for a notebook execution, identified by the notebook file id."""
    return TriggerActorModel(type=TriggerActorType.NOTEBOOK, id=str(notebook_id))


def chat_session_actor(chat_session_id: str) -> TriggerActorModel:
    """Actor for work driven by a chat session."""
    return TriggerActorModel(type=TriggerActorType.CHATSESSION, id=str(chat_session_id))


def file_actor(file_id: str) -> TriggerActorModel:
    """Actor for work driven by a file artifact."""
    return TriggerActorModel(type=TriggerActorType.FILE, id=str(file_id))


def scheduler_actor(trigger_id: str | None = None) -> TriggerActorModel:
    """Actor for the job scheduler, optionally identified by its trigger."""
    return TriggerActorModel(
        type=TriggerActorType.SCHEDULER, id=str(trigger_id) if trigger_id else None
    )


def event_actor(event_id: str) -> TriggerActorModel:
    """Actor for event-driven work, identified by the source event."""
    return TriggerActorModel(type=TriggerActorType.EVENT, id=str(event_id))


def system_actor(subsystem: str | None = None) -> TriggerActorModel:
    """Actor for internal system work, optionally naming the subsystem."""
    return TriggerActorModel(type=TriggerActorType.SYSTEM, id=subsystem)


def format_trigger_actor(actor: TriggerActorModel | None) -> str | None:
    """Render a human-readable label for logs, audit messages, and job context."""
    if actor is None:
        return None

    label = actor.type.value
    if actor.id:
        label = f"{label}:{actor.id}"
    return label


__all__ = [
    "agent_actor",
    "chat_session_actor",
    "event_actor",
    "file_actor",
    "format_trigger_actor",
    "notebook_actor",
    "scheduler_actor",
    "system_actor",
    "user_actor",
]
