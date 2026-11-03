from __future__ import annotations

from contextlib import contextmanager
from uuid import UUID, uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from kontext.data.database import Base
from kontext.data.models import ChatSession, QuerySession
from kontext.data.query_session_service import QuerySessionDataService
from kontext.schema import QuerySessionStatus


def _setup(project_id: str, service):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        execution_options={"schema_translate_map": {"project": None}},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)

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

    service._session_scope = session_scope  # type: ignore[method-assign]
    return factory


def _seed_service(project_id: str):
    service = QuerySessionDataService(project_id)
    factory = _setup(project_id, service)
    return service, factory


def test_invalidate_for_connection_is_scoped_and_clears_chat_links() -> None:
    project_id = str(uuid4())
    service, factory = _seed_service(project_id)
    connection_a = uuid4()
    connection_b = uuid4()
    session_a = uuid4()
    session_b = uuid4()
    chat_id = uuid4()

    with factory() as session:
        session.add(
            QuerySession(
                id=session_a,
                session_name="A",
                project_id=UUID(project_id),
                catalog_connection_id=connection_a,
                status=QuerySessionStatus.INITIALIZING.value,
                is_deleted=False,
            )
        )
        session.add(
            QuerySession(
                id=session_b,
                session_name="B",
                project_id=UUID(project_id),
                catalog_connection_id=connection_b,
                status=QuerySessionStatus.ACTIVE.value,
                is_deleted=False,
            )
        )
        session.add(
            ChatSession(
                id=chat_id,
                project_id=UUID(project_id),
                session_name="Chat",
                query_session_id=session_a,
            )
        )
        session.commit()

    invalidated = service.invalidate_sessions_for_catalog_connection(
        connection_a, "Catalog metadata changed"
    )

    assert invalidated == [session_a]
    # INITIALIZING sessions are invalidated too (not just ACTIVE).
    assert service.get_session(str(session_a)) is None
    assert service.get_session(str(session_b)) is not None
    with factory() as session:
        chat = session.get(ChatSession, chat_id)
        assert chat is not None
        assert chat.query_session_id is None
