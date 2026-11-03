"""Helper utilities for working with project models and summaries."""

import json

from kontext.schema import ProjectModel, ProjectNavModel


def generate_project_summary(project: ProjectModel, exclude_none: bool = True) -> str:
    """Generate a compact project summary from a ProjectModel.

    Creates a ProjectNavModel from the full ProjectModel and returns
    its JSON representation with camelCase field names.

    Args:
        project: The full project model
        exclude_none: Whether to exclude fields with None values

    Returns:
        JSON string with fields: id, projectName, projectCode, accessLevel
    """
    nav = ProjectNavModel(
        id=project.id,
        project_name=project.project_name,
        project_code=project.project_code,
        access_level=project.access_level,
    )
    # Use alias (camelCase) for API-compatible output
    try:
        return nav.model_dump_json(by_alias=True, exclude_none=exclude_none)
    except Exception:
        return nav.model_dump_json(by_alias=True, indent=None, exclude_none=exclude_none)


def generate_sql_scope_summary(
    project: ProjectModel,
    *,
    query_session_id: str | None = None,
    catalog_connection_id: str | None = None,
    default_namespace: str | None = None,
    default_entity_id: str | None = None,
    engine_type: str | None = None,
) -> str:
    """Generate project context plus the active SQL execution scope."""

    summary = generate_project_summary(project)
    scope = {
        "querySessionId": query_session_id,
        "defaultCatalogConnectionId": catalog_connection_id,
        "defaultNamespace": default_namespace,
        "defaultEntityId": default_entity_id,
        "engineType": engine_type,
    }
    active_scope = {key: value for key, value in scope.items() if value is not None}
    if not active_scope:
        return summary
    return f"{summary}\n\nActive SQL Scope:\n{json.dumps(active_scope, ensure_ascii=True)}"
