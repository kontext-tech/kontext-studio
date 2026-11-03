"""Single mapping layer between the HTTP transport and domain contracts.

The routers and service adapters used to re-implement ``QueryAccessContext`` and
``ChatAccessContext`` construction (four copies, already drifting on the
missing-project error type) and to translate domain service errors to
``HTTPException`` (three copies). Import these helpers instead so the mapping
and its error behavior cannot diverge per endpoint.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import HTTPException

from kontext.chat import ChatAccessContext
from kontext.query import QueryAccessContext
from kontext.schema import ChatSessionModel, QuerySessionModel

from .dependencies import AuthContext


def _require_project(auth_context: AuthContext[Any]) -> None:
    if auth_context.project is None:
        raise HTTPException(status_code=400, detail="Project context required")


def build_query_access_context(
    auth_context: AuthContext[Any],
    *,
    resource: QuerySessionModel | None = None,
) -> QueryAccessContext:
    """Build the canonical query access context from request auth state."""
    _require_project(auth_context)
    return QueryAccessContext(
        project_id=auth_context.project_id,
        user_id=auth_context.user_id,
        actor_label=auth_context.actor_label,
        effective_owner_id=auth_context.effective_owner_id,
        project_scope=auth_context.scope.value == "project",
        resource=resource,
    )


def build_chat_access_context(
    auth_context: AuthContext[Any],
    *,
    resource: ChatSessionModel | None = None,
) -> ChatAccessContext:
    """Build the canonical chat access context from request auth state."""
    _require_project(auth_context)
    user = auth_context.user
    return ChatAccessContext(
        project_id=auth_context.project_id,
        user_id=UUID(str(user.id)) if user else None,
        effective_owner_id=auth_context.effective_owner_id if user else None,
        project_scope=auth_context.scope.value == "project",
        project=auth_context.project,
        resource=resource,
        auth_manager=auth_context.auth_manager,
    )


def domain_error_to_http(exc: Any) -> HTTPException:
    """Translate a domain service error (``status_code``/``detail``) to HTTP."""
    return HTTPException(status_code=exc.status_code, detail=exc.detail)
