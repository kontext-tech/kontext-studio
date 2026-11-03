"""Base toolkit for Kontext tools with environment-aware service resolution."""

import json
import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol, TypeVar
from uuid import uuid4

from pydantic import BaseModel

from kontext.agent import (
    FrameworkToolkit,
    RuntimeToolContext,
    SharedArtifactDescriptor,
    SharedSessionStore,
    ToolResultEntry,
    ToolResultSidecar,
    get_session_state,
    get_tool_sidecar,
)
from kontext.agent import (
    link_artifact_to_session as helper_link_artifact_to_session,
)
from kontext.common.artifacts.provenance import build_data_identity_key
from kontext.common.protocols import (
    AIToolkitServiceProviderProtocol,
    IFileServiceProtocol,
    IProjectServiceProtocol,
    IQuerySessionServiceProtocol,
)
from kontext.schema import ArtifactProvenance, ArtifactType, QueryEngineType

from ..utils.tool_result_utils import tool_result_to_str

if TYPE_CHECKING:
    from kontext.schema import ChatSessionModel, InlineData, ProjectModel

T = TypeVar("T", bound=BaseModel)


class _HasSuccess(Protocol):
    """Minimal contract shared by every generated tool-result model."""

    @property
    def success(self) -> bool: ...


@dataclass(frozen=True)
class ToolkitScope:
    """Shared construction scope for Kontext toolkits.

    Carries the per-chat/toolkit context that every toolkit takes; blueprints
    build it once from the `AgentCreationContext` and pass it into each
    toolkit, instead of repeating eight identical kwargs per toolkit.
    """

    project: "ProjectModel"
    runtime_provider: "AIToolkitServiceProviderProtocol | None" = None
    session_id: str | None = None
    chat_session_id: str | None = None
    catalog_connection_id: str | None = None
    default_namespace: str | None = None
    default_entity_id: str | None = None
    engine_type: QueryEngineType | str | None = None

    @classmethod
    def from_context(cls, context: Any) -> "ToolkitScope":
        """Build a scope from an `AgentCreationContext` (lazy adapter import)."""
        from ..adapters import AgentCreationContext

        if not isinstance(context, AgentCreationContext):  # pragma: no cover - defensive
            raise TypeError(f"Expected AgentCreationContext, got {type(context)!r}")

        return cls(
            project=context.project,
            runtime_provider=context.runtime_provider,
            session_id=context.query_session_id,
            chat_session_id=context.session_id,
            catalog_connection_id=context.catalog_connection_id,
            default_namespace=context.default_namespace,
            default_entity_id=context.default_entity_id,
            engine_type=context.engine_type,
        )


class KontextToolkit(FrameworkToolkit):
    """Base toolkit class that provides local-first service resolution."""

    def _coerce_engine_type(
        self, engine_type: QueryEngineType | str | None
    ) -> QueryEngineType | None:
        """Normalize engine type values from enum, API payloads, or lowercase aliases."""
        if engine_type is None:
            return None

        if isinstance(engine_type, QueryEngineType):
            return engine_type

        normalized = str(engine_type).strip()
        if not normalized:
            return None

        try:
            return QueryEngineType(normalized)
        except ValueError:
            normalized_casefold = normalized.casefold()
            for candidate in QueryEngineType:
                if (
                    candidate.value.casefold() == normalized_casefold
                    or candidate.name.casefold() == normalized_casefold
                ):
                    return candidate
            return None

    def __init__(
        self,
        name: str,
        project: "ProjectModel | None" = None,
        runtime_provider: "AIToolkitServiceProviderProtocol | None" = None,
        session_id: str | None = None,
        chat_session_id: str | None = None,
        catalog_connection_id: str | None = None,
        default_namespace: str | None = None,
        default_entity_id: str | None = None,
        engine_type: QueryEngineType | str | None = None,
        scope: ToolkitScope | None = None,
        tools: list | None = None,
    ):
        """Initialize the Kontext toolkit.

        Args:
            name: Name of the toolkit
            project: The project model with full context
            runtime_provider: Optional runtime-provider override
            session_id: Optional query session ID
            chat_session_id: Optional chat session ID
            engine_type: Optional engine type (sticky context)
            scope: Optional `ToolkitScope` providing defaults for omitted args
            tools: List of tools to register
        """
        if scope is not None:
            project = project if project is not None else scope.project
            runtime_provider = (
                runtime_provider if runtime_provider is not None else scope.runtime_provider
            )
            session_id = session_id if session_id is not None else scope.session_id
            chat_session_id = (
                chat_session_id if chat_session_id is not None else scope.chat_session_id
            )
            catalog_connection_id = (
                catalog_connection_id
                if catalog_connection_id is not None
                else scope.catalog_connection_id
            )
            default_namespace = (
                default_namespace if default_namespace is not None else scope.default_namespace
            )
            default_entity_id = (
                default_entity_id if default_entity_id is not None else scope.default_entity_id
            )
            engine_type = engine_type if engine_type is not None else scope.engine_type

        if project is None:
            raise ValueError(f"{name} requires a project (directly or via scope)")

        super().__init__(
            name=name,
            tools=tools or [],
        )
        self.project = project
        self.project_id = project.id
        self.runtime_provider = runtime_provider
        self.session_id = session_id
        self.chat_session_id = chat_session_id
        self.catalog_connection_id = catalog_connection_id
        self.default_namespace = default_namespace
        self.default_entity_id = default_entity_id

        # Cast to QueryEngineType if provided as string
        if isinstance(engine_type, str):
            resolved_engine_type = self._coerce_engine_type(engine_type)
            if resolved_engine_type is None:
                self.engine_type = QueryEngineType.DUCKDB
            else:
                self.engine_type = resolved_engine_type
        else:
            self.engine_type = engine_type

        self.logger = logging.getLogger(__name__)

        # Per-system memoization. A toolkit instance is materialized per agent
        # system (one per chat request), so caching scope hydration avoids
        # re-fetching the chat session on every tool invocation while it stays
        # correct for the lifetime of that request.
        self._scope_hydration_attempted = False

    def _create_result(self, success: bool, result_class: type[BaseModel], **kwargs) -> str:
        """Create a standardized tool result string (JSON with side-loading).

        Args:
            success: Whether the operation succeeded
            result_class: The Pydantic model class for the result
            **kwargs: Additional fields for the result model
        """
        # Merge error into message if success is False
        if not success:
            error_val = kwargs.pop("error", None)
            msg = kwargs.get("message", "Operation failed")
            if error_val:
                kwargs["message"] = f"{msg}: {error_val}"

        res = result_class(success=success, **kwargs)
        return self._wrap_result(res)

    def get_file_service(self) -> IFileServiceProtocol | None:
        """Resolve the appropriate file service (local or client)."""
        service = self.runtime_provider.get_file_service() if self.runtime_provider else None
        return service

    def get_project_service(self) -> IProjectServiceProtocol | None:
        """Resolve the appropriate project service (local or client)."""
        return self.runtime_provider.get_project_service() if self.runtime_provider else None

    def get_query_session_service(self) -> IQuerySessionServiceProtocol | None:
        """Resolve the query session service."""
        service = (
            self.runtime_provider.get_query_session_service() if self.runtime_provider else None
        )
        return service

    async def get_chat_session(self) -> "ChatSessionModel | None":
        """Load the active chat session when the toolkit is operating in chat scope."""
        if not self.runtime_provider or not self.chat_session_id:
            return None

        chat_session_service = self.runtime_provider.get_chat_session_service()
        if chat_session_service is None:
            return None

        try:
            return await chat_session_service.get_session(str(self.chat_session_id))
        except Exception as exc:
            self.logger.warning(
                "Failed to load chat session %s for toolkit scope hydration: %s",
                self.chat_session_id,
                exc,
            )
            return None

    async def hydrate_query_scope_from_chat_session(self) -> None:
        """Populate missing SQL/query scope from the owning chat session when available."""
        if (
            self.session_id
            and self.catalog_connection_id
            and self.default_namespace
            and self.default_entity_id
            and self.engine_type is not None
        ):
            return

        # The chat session is a per-run constant source of scope; resolve it at
        # most once per toolkit instance instead of on every tool call.
        if self._scope_hydration_attempted:
            return
        self._scope_hydration_attempted = True

        chat_session = await self.get_chat_session()
        if chat_session is None:
            return

        if not self.session_id and chat_session.query_session_id:
            self.session_id = str(chat_session.query_session_id)

        if not self.catalog_connection_id and chat_session.default_catalog_connection_id:
            self.catalog_connection_id = str(chat_session.default_catalog_connection_id)

        if not self.default_namespace and chat_session.default_namespace:
            self.default_namespace = chat_session.default_namespace

        if not self.default_entity_id and chat_session.default_entity_id:
            self.default_entity_id = str(chat_session.default_entity_id)

        if self.engine_type is None and chat_session.engine_type:
            resolved_engine_type = self._coerce_engine_type(chat_session.engine_type)
            if resolved_engine_type is None:
                self.logger.warning(
                    "Ignoring invalid engine_type '%s' on chat session %s",
                    chat_session.engine_type,
                    self.chat_session_id,
                )
            else:
                self.engine_type = resolved_engine_type

    async def link_artifact_to_session(
        self,
        artifact_id: str,
        artifact_type: ArtifactType,
        title: str | None = None,
        meta: dict[str, Any] | None = None,
        run_context: RuntimeToolContext | None = None,
        register_shared_descriptor: bool = True,
        sql: str | None = None,
        identity_key: str | None = None,
        row_count: int | None = None,
        column_names: list[str] | None = None,
        provenance: ArtifactProvenance | None = None,
    ) -> bool:
        """Link an artifact (data table, chart, notebook) to the current chat session.

        Args:
            artifact_id: The ID of the artifact (file ID)
            artifact_type: The type of artifact
            title: Optional display name for the artifact in the session
            meta: Optional metadata for the artifact
            run_context: Optional runtime context for session state
            provenance: Optional organizational provenance embedded into the
                persisted artifact meta (``meta["provenance"]``)

        Returns:
            True if linked successfully, False otherwise
        """
        session_state = get_session_state(run_context)
        if register_shared_descriptor:
            self.upsert_artifact_descriptor(
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                title=title,
                sql=sql,
                identity_key=identity_key,
                row_count=row_count,
                column_names=column_names,
                run_context=run_context,
            )

        chat_session_service = (
            self.runtime_provider.get_chat_session_service() if self.runtime_provider else None
        )
        return await helper_link_artifact_to_session(
            project_id=self.project_id,
            session_id=self.chat_session_id,
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            title=title,
            meta=meta,
            session_state=session_state,
            chat_session_service=chat_session_service,
            register_shared_descriptor=False,
            provenance=provenance,
        )

    def _wrap_result(self, result: Any) -> str:
        """Wrap tool result for response reporting."""
        return tool_result_to_str(result)

    @staticmethod
    def _parse_result_model(raw: str, result_class: type[T]) -> T:
        """Parse a single-item tool result JSON into its typed result model.

        Batch tools delegate to the single-item tools and rehydrate each
        JSON result into its schema model so the aggregate payload stays typed.
        """
        return result_class.model_validate(json.loads(raw))

    async def _collect_batch_items(
        self,
        item_ids: Sequence[str],
        *,
        fetch: Callable[[str], Awaitable[str]],
        parse_into: type[T],
        failure: Callable[[str, Exception], T],
    ) -> list[T]:
        """Batch-fetch ids through the single-item tool and rehydrate typed results.

        ``fetch`` must return the single-item tool's JSON result; any fetch or
        parse failure is appended as a per-item failure built by ``failure`` so
        one bad id cannot sink the whole batch.
        """
        collected: list[T] = []
        for item_id in item_ids:
            try:
                raw = await fetch(item_id)
                collected.append(self._parse_result_model(raw, parse_into))
            except Exception as exc:
                collected.append(failure(item_id, exc))
        return collected

    @staticmethod
    def _failed_count(items: Sequence[_HasSuccess]) -> int:
        """Number of per-item results that report ``success=False``."""
        return sum(1 for item in items if item.success is False)

    def format_as_table(
        self,
        data: list[dict[str, Any]] | list[BaseModel],
        fields: list[str] | None = None,
        format: str = "markdown",
        max_items: int = 50,
        max_cell_chars: int = 80,
    ) -> str:
        """Format a list of objects as a table (Markdown or CSV).

        Args:
            data: List of objects (dictionaries or Pydantic models)
            fields: List of fields to include. If None, all fields from the first item are used.
            format: Output format ('markdown' or 'csv')
            max_items: Maximum number of items to include
            max_cell_chars: Maximum characters per cell (truncated with ...)

        Returns:
            Formatted string table
        """
        if not data:
            return ""

        # Normalize data to list of dicts
        items: list[dict[str, Any]] = []
        for i, item in enumerate(data):
            if i >= max_items:
                break
            if isinstance(item, BaseModel):
                items.append(item.model_dump())
            else:
                items.append(item)

        if not items:
            return ""

        # Determine fields
        if not fields:
            fields = list(items[0].keys())

        def truncate(val: Any) -> str:
            s = str(val).replace("\n", " ").replace("\r", " ").strip()
            if len(s) > max_cell_chars:
                return s[:max_cell_chars].strip() + "..."
            return s

        if format == "csv":
            import csv
            import io

            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            for item in items:
                writer.writerow({f: truncate(item.get(f, "")) for f in fields})
            result = output.getvalue().strip()
            if len(data) > max_items:
                result += f"\n(truncated; showing {max_items} of {len(data)} items)"
            return result

        # Markdown format
        header = "| " + " | ".join(fields) + " |"
        separator = "| " + " | ".join(["---"] * len(fields)) + " |"
        rows = []
        for item in items:
            row = "| " + " | ".join([truncate(item.get(f, "")) for f in fields]) + " |"
            rows.append(row)

        result = "\n".join([header, separator, *rows])
        if len(data) > max_items:
            result += f"\n\n*(Table truncated; showing {max_items} of {len(data)} items)*"
        return result

    def register_transient_artifact(
        self,
        payload: Any,
        artifact_type: ArtifactType,
        *,
        transient_id: str | None = None,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """Register a local-run artifact payload under an explicit handle.

        The payload is stored once in the session's tool-result sidecar, keyed
        by the handle itself — never by a hash of its serialized form.
        """
        if transient_id is None:
            transient_id = str(uuid4())

        sidecar = self._tool_sidecar()
        if sidecar is None:
            self.logger.warning(
                "No tool-result sidecar active; artifact %s not retained (sid=%s)",
                transient_id,
                self.chat_session_id,
            )
            return transient_id

        sidecar.put(
            transient_id,
            ToolResultEntry(
                payload=payload,
                artifact_type=artifact_type.value,
                title=title,
                metadata=dict(metadata or {}),
            ),
        )

        return transient_id

    def get_transient_data(self, data_table_id: str) -> "InlineData | None":
        """Retrieve a local transient data-table payload as typed ``InlineData``."""
        result = self.get_transient_artifact(data_table_id, artifact_type=ArtifactType.DATATABLE)
        if result is None:
            return None

        from kontext.schema import InlineData

        if isinstance(result, InlineData):
            return result

        return None

    def get_transient_artifact(
        self,
        artifact_id: str,
        *,
        artifact_type: ArtifactType | None = None,
    ) -> Any | None:
        """Retrieve a local-run artifact payload by explicit handle."""
        entry = self._sidecar_entry(artifact_id)
        if entry is None:
            return None

        if artifact_type is not None and entry.artifact_type != artifact_type.value:
            return None

        return entry.payload

    def _tool_sidecar(self) -> ToolResultSidecar | None:
        """Resolve the session's sidecar by chat-session id.

        Resolution goes through the session registry (not ``run_context``) so
        read-heavy tools that never receive a runtime context can still reach
        the run's sidecar.
        """
        return get_tool_sidecar(self.chat_session_id)

    def _sidecar_entry(self, artifact_id: str) -> ToolResultEntry | None:
        """Resolve a sidecar entry by handle (including alias chains)."""
        sidecar = self._tool_sidecar()
        return sidecar.get(artifact_id) if sidecar is not None else None

    async def resolve_data_table_id(
        self, data_table_id: str, run_context: RuntimeToolContext | None = None
    ) -> str:
        """Resolve a data handle to a durable data-table file ID."""
        from kontext.schema import InlineData

        payload = self.get_transient_data(data_table_id)
        resolved_id = await self.ensure_persistent_artifact(
            artifact_id=data_table_id,
            artifact_type=ArtifactType.DATATABLE,
            payload=payload,
            run_context=run_context,
            promote_artifact=self._promote_inline_data_file,
            title=(payload.title if payload else None),
        )
        if payload is not None and not isinstance(payload, InlineData):
            raise ValueError(
                f"Could not resolve valid InlineData from transient ID {data_table_id}"
            )
        return resolved_id

    async def ensure_persistent_artifact(
        self,
        artifact_id: str,
        artifact_type: ArtifactType,
        *,
        payload: Any | None = None,
        run_context: RuntimeToolContext | None = None,
        promote_artifact: Callable[..., Awaitable[str]],
        title: str | None = None,
        meta: dict[str, Any] | None = None,
        register_shared_descriptor: bool = True,
        sql: str | None = None,
        identity_key: str | None = None,
        row_count: int | None = None,
        column_names: list[str] | None = None,
        provenance: ArtifactProvenance | None = None,
    ) -> str:
        """Resolve or promote a local artifact handle into a durable artifact reference."""
        from contextlib import suppress

        file_service = self.get_file_service()
        if file_service and await file_service.exists_by_id(
            project_id=self.project_id, file_id=artifact_id
        ):
            return artifact_id

        shared_id = self.resolve_shared_artifact_id(artifact_id, run_context=run_context)
        if shared_id:
            return shared_id

        promoted_id = self.get_promoted_artifact_id(artifact_id)
        if promoted_id:
            self.register_artifact_alias(artifact_id, promoted_id, run_context=run_context)
            return promoted_id

        payload = (
            payload
            if payload is not None
            else self.get_transient_artifact(artifact_id, artifact_type=artifact_type)
        )
        if payload is None:
            raise ValueError(
                f"{artifact_type.value} with ID '{artifact_id}' is not available in local run state or shared session state."
            )

        persisted_title = title or self.get_local_artifact_title(artifact_id) or "Untitled"
        persisted_id = await promote_artifact(
            payload, persisted_title, sql=sql, provenance=provenance
        )

        source_entry = self._sidecar_entry(artifact_id)
        if source_entry is not None:
            source_entry.durable_id = persisted_id
        self.register_artifact_alias(artifact_id, persisted_id, run_context=run_context)

        # Cache the promoted payload locally under its durable ID so same-run
        # consumers resolve it without a file-store round trip.
        with suppress(Exception):
            sidecar = self._tool_sidecar()
            if sidecar is not None:
                sidecar.put(
                    persisted_id,
                    ToolResultEntry(
                        payload=payload,
                        artifact_type=artifact_type.value,
                        title=persisted_title,
                        metadata=dict(source_entry.metadata) if source_entry else {},
                        durable_id=persisted_id,
                    ),
                )

        await self.link_artifact_to_session(
            artifact_id=persisted_id,
            artifact_type=artifact_type,
            title=persisted_title,
            meta=meta,
            run_context=run_context,
            register_shared_descriptor=register_shared_descriptor,
            sql=sql,
            identity_key=identity_key,
            row_count=row_count,
            column_names=column_names,
            provenance=provenance,
        )

        self.logger.info(
            "Promoted transient %s %s to durable artifact %s",
            artifact_type.value,
            artifact_id,
            persisted_id,
        )
        return persisted_id

    def get_promoted_artifact_id(self, artifact_id: str) -> str | None:
        """Return the durable ID a local handle was promoted to, if any."""
        entry = self._sidecar_entry(artifact_id)
        return entry.durable_id if entry is not None else None

    def get_local_artifact_title(self, artifact_id: str) -> str | None:
        """Return the local-run title recorded for a handle."""
        entry = self._sidecar_entry(artifact_id)
        return entry.title if entry is not None else None

    async def _promote_inline_data_file(
        self,
        payload: Any,
        name: str | None,
        *,
        sql: str | None = None,
        provenance: ArtifactProvenance | None = None,
    ) -> str:
        from kontext.schema import InlineData

        if not isinstance(payload, InlineData):
            raise ValueError("Only InlineData payloads can be promoted as data-table files.")

        file_service = self.get_file_service()
        if not file_service:
            raise ValueError("File service not available for artifact promotion")

        # Use the same canonical materialization path as the query job so the
        # promoted artifact carries a columnar row store and provenance,
        # regardless of which process promotes it.
        materialized_id = await file_service.materialize_inline_data(
            project_id=self.project_id,
            inline_data=payload,
            name=name or payload.title or "Untitled Data Table",
            session_id=self.session_id,
            chat_session_id=self.chat_session_id,
            sql=sql,
            provenance=provenance,
        )
        if materialized_id is None:
            raise ValueError("Inline data payload had no table to materialize.")
        return materialized_id

    # Shared Session State Management
    def get_shared_session_store(
        self, run_context: RuntimeToolContext | None = None
    ) -> SharedSessionStore | None:
        """Return the typed shared session store for the current run context."""
        return SharedSessionStore.from_session_state(get_session_state(run_context))

    def build_data_identity_key(self, sql: str) -> str:
        """Build a stable result identity key from SQL and the toolkit execution scope."""
        return build_data_identity_key(
            sql,
            catalog_connection_id=self.catalog_connection_id,
            default_namespace=self.default_namespace,
            default_entity_id=self.default_entity_id,
            engine_type=self.engine_type,
        )

    def upsert_artifact_descriptor(
        self,
        *,
        artifact_id: str,
        artifact_type: ArtifactType,
        title: str | None = None,
        sql: str | None = None,
        identity_key: str | None = None,
        row_count: int | None = None,
        column_names: list[str] | None = None,
        run_context: RuntimeToolContext | None = None,
    ) -> SharedArtifactDescriptor | None:
        """Upsert a durable artifact descriptor into shared session state."""
        store = self.get_shared_session_store(run_context)
        if store is None:
            self.logger.debug("RunContext not available, skipping shared artifact registration")
            return None

        return store.upsert_artifact_descriptor(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            title=title,
            sql=sql,
            identity_key=identity_key,
            row_count=row_count,
            column_names=column_names,
        )

    def get_artifact_descriptor(
        self, artifact_id: str, run_context: RuntimeToolContext | None = None
    ) -> SharedArtifactDescriptor | None:
        """Resolve a shared artifact descriptor by durable ID."""
        store = self.get_shared_session_store(run_context)
        if store is None:
            return None
        return store.get_artifact_descriptor(artifact_id)

    def resolve_shared_artifact_id(
        self,
        artifact_id: str,
        run_context: RuntimeToolContext | None = None,
    ) -> str | None:
        """Resolve a durable artifact ID from the shared session registry."""
        store = self.get_shared_session_store(run_context)
        if store is None:
            return None
        return store.resolve_artifact_id(artifact_id)

    def register_artifact_alias(
        self,
        alias_id: str,
        artifact_id: str,
        *,
        run_context: RuntimeToolContext | None = None,
    ) -> str | None:
        """Register a durable shared alias for a promoted local handle."""
        store = self.get_shared_session_store(run_context)
        if store is None:
            return None
        return store.register_artifact_alias(alias_id, artifact_id)

    def list_artifact_descriptors(
        self,
        run_context: RuntimeToolContext | None = None,
        artifact_type: ArtifactType | None = None,
    ) -> list[SharedArtifactDescriptor]:
        """List shared artifact descriptors for the current session."""
        store = self.get_shared_session_store(run_context)
        if store is None:
            return []
        return store.list_artifact_descriptors(artifact_type=artifact_type)

    def find_data_artifact_by_identity(
        self, identity_key: str, run_context: RuntimeToolContext | None = None
    ) -> SharedArtifactDescriptor | None:
        """Resolve a shared data-table artifact from the identity index."""
        store = self.get_shared_session_store(run_context)
        if store is None:
            return None
        return store.find_data_artifact_by_identity(identity_key)
