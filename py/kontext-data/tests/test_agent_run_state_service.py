"""Tests for the neutral harness run-state persistence service.

`AgentRunStateDataService` implements `kontext.agent.persistence.SessionPersistence`
(storage for the stateless-harness design; see docs/ai/harness-abstraction.md).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from kontext.agent.persistence import MessageRecord, SessionPersistence
from kontext.data.agent_run_state_service import AgentRunStateDataService
from kontext.data.database import Base
from kontext.schema import ChatMessage, ChatMessageStatus, ChatMessageType

if TYPE_CHECKING:
    from collections.abc import Callable, Generator

_SESSION_ID = "c5dcdeff-aba0-43e0-95a4-b60074a01381"


@pytest.fixture()
def service(
    tmp_path,
) -> Generator[tuple[AgentRunStateDataService, Callable[[], object]], None, None]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'run-state.db'}",
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"project": None}},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    svc = AgentRunStateDataService(str(uuid4()))

    @contextmanager
    def session_scope(*, commit: bool = True):
        session = factory()
        try:
            yield session
            if commit:
                session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    svc._session_scope = session_scope  # type: ignore[method-assign]
    yield svc, session_scope


def test_service_complies_with_neutral_persistence_protocol(service) -> None:
    svc, _ = service
    assert isinstance(svc, SessionPersistence)


@pytest.mark.asyncio
async def test_message_snapshot_roundtrips_wire_shape(service) -> None:
    svc, _ = service
    message = ChatMessage(
        id="msg-1",
        type=ChatMessageType.ASSISTANT,
        status=ChatMessageStatus.COMPLETED,
        segments=[],
    )
    records = [
        MessageRecord(
            session_id=_SESSION_ID,
            message_json=message.model_dump_json(),
            seq=index,
        )
        for index in range(2)
    ]

    await svc.replace_session_messages(_SESSION_ID, [records[0]])
    await svc.replace_session_messages(_SESSION_ID, records)

    stored = await svc.list_messages(_SESSION_ID)
    assert len(stored) == 2, "snapshot writes must be idempotent full-replacements"
    assert [record.seq for record in stored] == [0, 1]
    roundtripped = ChatMessage.model_validate_json(stored[0].message_json)
    assert roundtripped.id == "msg-1"


@pytest.mark.asyncio
async def test_message_seq_falls_back_to_enumeration_order(service) -> None:
    svc, _ = service
    await svc.replace_session_messages(
        _SESSION_ID,
        [
            MessageRecord(session_id=_SESSION_ID, message_json="{}"),
            MessageRecord(session_id=_SESSION_ID, message_json="{}"),
        ],
    )

    stored = await svc.list_messages(_SESSION_ID)
    assert [record.seq for record in stored] == [0, 1]


@pytest.mark.asyncio
async def test_chat_session_delete_cascades_run_state(service) -> None:
    """DoD: deleting a chat session removes the message snapshot and the
    harness-internal blob in the same transaction."""
    svc, session_scope = service

    chat_session_id = str(uuid4())  # dashed UUID string, as chat sessions key run state
    await svc.replace_session_messages(
        chat_session_id,
        [MessageRecord(session_id=chat_session_id, message_json="{}", seq=0)],
    )
    await svc.save_harness_state(chat_session_id, "{}")
    unrelated_session = uuid4().hex
    await svc.replace_session_messages(
        unrelated_session,
        [MessageRecord(session_id=unrelated_session, message_json="{}", seq=0)],
    )

    from kontext.data.chat_session_service import ChatSessionDataService
    from kontext.data.models import ChatSession

    project_id = uuid4()
    chat_service = ChatSessionDataService(str(project_id))

    @contextmanager
    def shared_scope(*, commit: bool = True):
        with session_scope(commit=commit) as session:
            yield session

    chat_service._session_scope = shared_scope  # type: ignore[method-assign]
    with session_scope() as session:
        session.add(
            ChatSession(
                id=UUID(chat_session_id),
                project_id=project_id,
                session_name="deleteme",
                is_deleted=False,
            )
        )

    await chat_service.delete_session_async(chat_session_id, user_id=None)

    assert await svc.list_messages(chat_session_id) == []
    assert await svc.load_harness_state(chat_session_id) is None
    # other sessions untouched
    assert len(await svc.list_messages(unrelated_session)) == 1


@pytest.mark.asyncio
async def test_harness_state_blob_roundtrip(service) -> None:
    svc, _ = service
    blob = '{"session_id": "s", "runs": [{"run_id": "r"}]}'
    assert await svc.load_harness_state(_SESSION_ID) is None

    await svc.save_harness_state(_SESSION_ID, blob)
    assert await svc.load_harness_state(_SESSION_ID) == blob
    await svc.save_harness_state(_SESSION_ID, "{}")  # overwrite
    assert await svc.load_harness_state(_SESSION_ID) == "{}"
