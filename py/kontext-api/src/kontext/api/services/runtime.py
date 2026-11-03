"""API-side runtime provider helpers."""

from __future__ import annotations

from collections.abc import Mapping
from uuid import UUID

from kontext.auth import AuthManager
from kontext.chat import ChatRuntimeProviderFactoryProtocol
from kontext.common.messaging import IQueueClient
from kontext.common.protocols import RuntimeProviderProtocol
from kontext.query import QueryAccessContext
from kontext.query.runtime_query_session_service import (
    AuthorizedRuntimeQuerySessionService,
)
from kontext.runtime.providers.local import LocalRuntimeProvider


def build_authorized_runtime_provider(
    *,
    project_id: str,
    access_context: QueryAccessContext,
    queue_client: IQueueClient | None,
) -> LocalRuntimeProvider:
    """Create an in-process runtime provider with canonical query behavior."""
    query_session_service = AuthorizedRuntimeQuerySessionService(
        access_context=access_context,
        queue_client=queue_client,
    )
    return LocalRuntimeProvider(
        project_id=project_id,
        query_session_service=query_session_service,
    )


class LocalHeadersRuntimeFactory(ChatRuntimeProviderFactoryProtocol):
    """Bare (headers-only) runtime provider factory for no-SQL service paths.

    The composition lives here, in the composition root, because the local
    deployment profile (auth refresh + ``LocalRuntimeProvider``) is not a
    neutral-layer concern: lower layers must never import the provider
    implementation.

    It resolves no owner-scoped query access, so callers must only use it for
    paths that never execute user SQL — service resolution (catalog
    management, knowledge curation, agent session-state reads) and CLI jobs.
    Streaming and execution paths must use
    ``build_authorized_runtime_provider`` instead, which injects an
    ``AuthorizedRuntimeQuerySessionService`` bound to the request's auth
    context.
    """

    async def create_runtime_provider(
        self,
        *,
        project_id: UUID | str,
        headers: Mapping[str, str],
    ) -> RuntimeProviderProtocol:
        auth_manager = AuthManager.from_headers(headers)
        await auth_manager.refresh_if_needed()
        return LocalRuntimeProvider(project_id=str(project_id))


LOCAL_HEADERS_RUNTIME_FACTORY = LocalHeadersRuntimeFactory()
