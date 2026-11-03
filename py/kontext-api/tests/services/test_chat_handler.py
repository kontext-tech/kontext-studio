"""
Tests for ChatHandler service.
"""

import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from kontext.agentic.chat_handler import ChatHandler
from kontext.common.utils.datetime_utils import utc_now
from kontext.schema import (
    ArtifactAction,
    ArtifactType,
    ChatAttachmentContext,
    ChatAttachmentContextFile,
    ChatAttachmentContextTable,
    ChatRequest,
    ChatSessionArtifactModel,
    ChatSessionModel,
    EventData,
    FileFormatType,
    NotebookMutationResult,
    NotebookUpsertBlockAction,
    NotebookUpsertBlockActionPayload,
    PythonExecutionApprovalMode,
    RunEvent,
    SimpleRunEvent,
    ToolCall,
    ToolCallCompletedEventData,
    ToolCallResult,
)


class MockEventStream:
    """Simple async iterator for streaming test events."""

    def __init__(self, events, error: Exception | None = None):
        self._events = iter(events)
        self._error = error
        self._error_raised = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._error and not self._error_raised:
            self._error_raised = True
            raise self._error

        try:
            return next(self._events)
        except StopIteration:
            raise StopAsyncIteration from None


class TestChatHandler:
    """Test cases for ChatHandler class."""

    @pytest.fixture
    def chat_handler(self):
        """ChatHandler instance for testing."""
        return ChatHandler()

    @pytest.fixture
    def mock_agent(self):
        """Mock agentic system."""

        class DummyAgent(SimpleNamespace):
            def bind_current_execution_run_id(self, current_execution_run_id: str | None) -> None:
                self.current_execution_run_id = current_execution_run_id

        return DummyAgent()

    @pytest.fixture
    def sample_events(self):
        """Sample neutral run events for testing."""
        return [
            SimpleRunEvent(event_type=RunEvent.RUNCONTENT, content="Hello "),
            SimpleRunEvent(event_type=RunEvent.RUNCONTENT, content="world!"),
            SimpleRunEvent(event_type=RunEvent.RUNCOMPLETED, content="Stream complete"),
        ]

    @pytest.fixture
    def mock_request(self):
        """Mock transport context."""
        project_id = str(uuid.uuid4())
        return {
            "project_id": project_id,
            "headers": {"Authorization": "Bearer mock-token"},
        }


class TestStreamAgentResponse:
    """Test cases for stream_agent_response method."""

    @pytest.fixture
    def chat_handler(self):
        """ChatHandler instance for testing."""
        return ChatHandler()

    @pytest.fixture
    def mock_agent(self):
        """Mock agentic system."""

        class DummyAgent(SimpleNamespace):
            def bind_current_execution_run_id(self, current_execution_run_id: str | None) -> None:
                self.current_execution_run_id = current_execution_run_id

        return DummyAgent()

    @pytest.fixture
    def sample_events(self):
        """Sample neutral run events for testing."""
        return [
            SimpleRunEvent(event_type=RunEvent.RUNCONTENT, content="Hello "),
            SimpleRunEvent(event_type=RunEvent.RUNCONTENT, content="world!"),
            SimpleRunEvent(event_type=RunEvent.RUNCOMPLETED, content="Stream complete"),
        ]

    @pytest.mark.asyncio
    async def test_successful_streaming(self, chat_handler, mock_agent, sample_events):
        """Test successful streaming of agent responses."""

        async def mock_stream_response(*args, **kwargs):
            for event in sample_events:
                # Agentic systems yield neutral SimpleRunEvent objects.
                yield event
            yield SimpleRunEvent(event_type=RunEvent.RUNCOMPLETED, content="Done")

        mock_agent.stream_response = mock_stream_response

        events = []
        async for event_json in chat_handler.stream_agent_response(mock_agent, "Hello"):
            event_data = json.loads(event_json.strip())
            events.append(event_data)

        # Should have content events and completion event
        assert len(events) >= 2
        assert any(e.get("eventType") == "RunContent" for e in events)
        assert any(e.get("eventType") == "RunCompleted" for e in events)

    @pytest.mark.asyncio
    async def test_streaming_with_session_and_user(self, chat_handler, mock_agent):
        """Test streaming with session_id and user_id."""

        async def mock_stream_response(message, session_id=None, user_id=None, **kwargs):
            assert session_id is not None
            assert user_id is not None
            yield SimpleRunEvent(event_type=RunEvent.RUNCOMPLETED, content="Done")

        mock_agent.stream_response = mock_stream_response

        session_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())

        events = []
        async for event_json in chat_handler.stream_agent_response(
            mock_agent, "Hello", session_id=session_id, user_id=user_id
        ):
            events.append(json.loads(event_json.strip()))

        assert len(events) > 0

    @pytest.mark.asyncio
    async def test_agent_error_handling(self, chat_handler, mock_agent):
        """Test error handling in agent streaming."""

        async def mock_stream_response(*args, **kwargs):
            yield SimpleRunEvent(event_type=RunEvent.RUNERROR, error_details="Agent failed")

        mock_agent.stream_response = mock_stream_response

        events = []
        async for event_json in chat_handler.stream_agent_response(mock_agent, "Hello"):
            events.append(json.loads(event_json.strip()))

        # Should have error event
        assert len(events) > 0
        assert any(e.get("eventType") == "RunError" for e in events)

    @pytest.mark.asyncio
    async def test_emits_artifact_event_immediately_after_tool_completion(
        self, chat_handler, mock_agent
    ):
        session_id = str(uuid.uuid4())
        artifact_id = str(uuid.uuid4())

        async def mock_stream_response(*args, **kwargs):
            _ = args, kwargs
            yield SimpleRunEvent(
                event_type=RunEvent.TOOLCALLCOMPLETED,
                event_data=EventData(
                    root=ToolCallCompletedEventData(
                        tool=ToolCall(
                            tool_call_id="tool-1",
                            tool_name="create_notebook",
                            result=ToolCallResult(
                                root=NotebookMutationResult(
                                    success=True,
                                    message="created",
                                    notebook_id=artifact_id,
                                    actions=[
                                        ArtifactAction(
                                            root=NotebookUpsertBlockAction(
                                                sequence=1,
                                                action_type="upsertBlock",
                                                payload=NotebookUpsertBlockActionPayload(
                                                    cid="block-1",
                                                    block_type="paragraph",
                                                    data={"content": "hi"},
                                                ),
                                            )
                                        )
                                    ],
                                )
                            ),
                        )
                    )
                ),
            )
            yield SimpleRunEvent(event_type=RunEvent.RUNCOMPLETED, content="Done")

        class _ChatSessionService:
            async def list_artifacts(self, requested_session_id: str):
                timestamp = datetime(2026, 5, 8, tzinfo=UTC)
                assert requested_session_id == session_id
                return [
                    ChatSessionArtifactModel(
                        id=str(uuid.uuid4()),
                        session_id=session_id,
                        artifact_id=artifact_id,
                        artifact_type=ArtifactType.NOTEBOOK,
                        title="Notebook",
                        created_at=timestamp,
                        updated_at=timestamp,
                    )
                ]

            async def update_token_usage(self, *args, **kwargs):
                _ = args, kwargs
                return None

        mock_agent.stream_response = mock_stream_response

        events = []
        async for event_json in chat_handler.stream_agent_response(
            mock_agent,
            "Hello",
            session_id=session_id,
            project_id=str(uuid.uuid4()),
            chat_session_service=_ChatSessionService(),
        ):
            events.append(json.loads(event_json.strip()))

        assert [event["eventType"] for event in events] == [
            "ToolCallCompleted",
            "ArtifactEvent",
            "RunCompleted",
        ]
        assert events[1]["eventData"]["artifact"]["artifactId"] == artifact_id


class TestCreateAgent:
    """Test cases for create_agent method."""

    @pytest.fixture
    def chat_handler(self):
        """ChatHandler instance for testing."""
        return ChatHandler()

    @pytest.fixture
    def chat_request(self):
        """Valid ChatRequest for testing."""
        return ChatRequest(
            project_id=str(uuid.uuid4()),
            session_id=str(uuid.uuid4()),
            message="Hello AI!",
        )

    @pytest.fixture
    def mock_provider(self):
        """Mock service provider."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_creates_agent_with_correct_params(
        self, chat_handler, chat_request, mock_provider
    ):
        """Test that agent is created with correct parameters."""
        user_id = str(uuid.uuid4())
        mock_project = MagicMock()

        with (
            patch("kontext.agentic.chat_context.AgentConfigBuilder") as mock_config_builder,
            patch("kontext.agentic.chat_handler.create_agentic_system") as mock_create_agent,
        ):
            mock_config = MagicMock()
            mock_config_builder.from_runtime_provider.return_value = mock_config
            mock_agent = MagicMock()
            mock_create_agent.return_value = mock_agent

            result = await chat_handler.create_agent(
                chat_request, mock_provider, mock_project, user_id=user_id
            )

            assert result == mock_agent
            mock_create_agent.assert_called_once()
            _kwargs = mock_create_agent.call_args.kwargs
            context = _kwargs["context"]
            assert context.config == mock_config
            assert context.project == mock_project
            assert not hasattr(context, "project_id")
            assert context.runtime_provider == mock_provider
            assert context.session_id == str(chat_request.session_id)
            assert context.user_id == user_id
            assert not hasattr(context, "model_id")
            assert context.query_session_id is None
            assert context.catalog_connection_id is None
            assert context.default_namespace is None
            assert context.default_entity_id is None
            assert context.engine_type is None

    @pytest.mark.asyncio
    async def test_creates_agent_with_attached_data_context(
        self, chat_handler, chat_request, mock_provider
    ):
        user_id = str(uuid.uuid4())
        project_id = str(uuid.uuid4())
        mock_project = MagicMock()
        mock_project.id = project_id
        session = ChatSessionModel(
            id=str(chat_request.session_id),
            project_id=str(chat_request.project_id),
            session_name="Attached files chat",
            date_created=utc_now(),
            python_execution_approval_mode=PythonExecutionApprovalMode.ALWAYSASK,
            is_deleted=False,
        )
        file_id = str(uuid.uuid4())
        attachment_context = ChatAttachmentContext(
            upload_preparation_run_id=str(uuid.uuid4()),
            internal_catalog_connection_id=str(uuid.uuid4()),
            files=[
                ChatAttachmentContextFile(
                    file_id=file_id,
                    file_name="Financial Sample.xlsx",
                    file_type=FileFormatType.EXCEL,
                )
            ],
            tables=[
                ChatAttachmentContextTable(
                    file_id=file_id,
                    entity_id=str(uuid.uuid4()),
                    namespace_name="bronze",
                    entity_name="Financial_Sample_Sheet1",
                    row_count=700,
                    column_names=["Segment", "Country", "Product"],
                )
            ],
        )

        with (
            patch("kontext.agentic.chat_context.AgentConfigBuilder") as mock_config_builder,
            patch("kontext.agentic.chat_handler.create_agentic_system") as mock_create_agent,
            patch(
                "kontext.agentic.chat_context.ChatSessionDataService.get_session_resolved_model_config_async",
                new=AsyncMock(return_value=None),
            ),
            patch(
                "kontext.agentic.chat_context.ChatSessionDataService.get_attachment_context_async",
                new=AsyncMock(return_value=attachment_context),
            ),
        ):
            mock_config = MagicMock()
            mock_config_builder.from_runtime_provider.return_value = mock_config
            mock_agent = MagicMock()
            mock_create_agent.return_value = mock_agent

            result = await chat_handler.create_agent(
                chat_request,
                mock_provider,
                mock_project,
                user_id=user_id,
                session=session,
            )

            assert result == mock_agent
            context = mock_create_agent.call_args.kwargs["context"]
            assert context.attached_data_sources is not None
            assert len(context.attached_data_sources) == 1
            assert context.attached_data_sources[0].file_name == "Financial Sample.xlsx"
            assert context.attached_data_summary is not None
            assert "Financial Sample.xlsx" in context.attached_data_summary
            assert "bronze.Financial_Sample_Sheet1" in context.attached_data_summary
