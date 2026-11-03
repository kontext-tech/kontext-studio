"""Framework-agnostic agent core for Kontext."""

from kontext.common.artifacts.provenance import build_data_identity_key

from .artifacts import (
    add_artifact_to_state,
    link_artifact_to_session,
)
from .client_policy import (
    ToolCallClientPolicy,
    get_tool_call_client_policy,
    sanitize_chat_messages_for_client,
    should_emit_reasoning_to_client,
    should_emit_tool_call_to_client,
    should_include_tool_call_details_for_client,
)
from .context import (
    AgentContext,
    RuntimeToolContext,
    ToolExecutionContext,
    agent_context_scope,
    get_session_state,
    get_tool_context,
    get_tool_sidecar,
    unregister_session_context,
)
from .harness import (
    HARNESS_ENTRY_POINT_GROUP,
    AgentCreationContext,
    AgentFrameworkAdapter,
    get_framework_adapter,
    get_harness_loggers,
    register_framework_adapter,
    seed_harness_logger_env,
)
from .metadata import AgentDescriptor, AgentKind
from .persistence import (
    InMemorySessionPersistence,
    MessageRecord,
    SessionPersistence,
)
from .shared_session_store import (
    KONTEXT_SESSION_ARTIFACT_ALIASES_KEY,
    KONTEXT_SESSION_ARTIFACTS_KEY,
    KONTEXT_SESSION_ATTACHED_DATA_SOURCES_KEY,
    KONTEXT_SESSION_CURRENT_EXECUTION_RUN_ID_KEY,
    KONTEXT_SESSION_DATA_IDENTITY_INDEX_KEY,
    KONTEXT_SESSION_NAMESPACE,
    SharedArtifactDescriptor,
    SharedSessionStore,
    create_kontext_session_state,
)
from .spec import (
    AgentSpec,
    collect_tools,
    normalize_agent_kind,
)
from .system import BaseAgenticSystem, StreamOptions
from .tool_results import (
    InMemoryToolResultSidecar,
    ToolResultEntry,
    ToolResultSidecar,
)
from .tool_schemas import render_spec_schema, render_tool_schema
from .toolkits import (
    FrameworkToolkit,
    ToolCallable,
    ToolRuntimeSpec,
    get_tool_runtime_spec,
)

__all__ = [
    "HARNESS_ENTRY_POINT_GROUP",
    "KONTEXT_SESSION_ARTIFACTS_KEY",
    "KONTEXT_SESSION_ARTIFACT_ALIASES_KEY",
    "KONTEXT_SESSION_ATTACHED_DATA_SOURCES_KEY",
    "KONTEXT_SESSION_CURRENT_EXECUTION_RUN_ID_KEY",
    "KONTEXT_SESSION_DATA_IDENTITY_INDEX_KEY",
    "KONTEXT_SESSION_NAMESPACE",
    "AgentContext",
    "AgentCreationContext",
    "AgentDescriptor",
    "AgentFrameworkAdapter",
    "AgentKind",
    "AgentSpec",
    "BaseAgenticSystem",
    "FrameworkToolkit",
    "InMemorySessionPersistence",
    "InMemoryToolResultSidecar",
    "MessageRecord",
    "RuntimeToolContext",
    "SessionPersistence",
    "SharedArtifactDescriptor",
    "SharedSessionStore",
    "StreamOptions",
    "ToolCallClientPolicy",
    "ToolCallable",
    "ToolExecutionContext",
    "ToolResultEntry",
    "ToolResultSidecar",
    "ToolRuntimeSpec",
    "add_artifact_to_state",
    "agent_context_scope",
    "build_data_identity_key",
    "collect_tools",
    "create_kontext_session_state",
    "get_framework_adapter",
    "get_harness_loggers",
    "get_session_state",
    "get_tool_call_client_policy",
    "get_tool_context",
    "get_tool_runtime_spec",
    "get_tool_sidecar",
    "link_artifact_to_session",
    "normalize_agent_kind",
    "register_framework_adapter",
    "render_spec_schema",
    "render_tool_schema",
    "sanitize_chat_messages_for_client",
    "seed_harness_logger_env",
    "should_emit_reasoning_to_client",
    "should_emit_tool_call_to_client",
    "should_include_tool_call_details_for_client",
    "unregister_session_context",
]
