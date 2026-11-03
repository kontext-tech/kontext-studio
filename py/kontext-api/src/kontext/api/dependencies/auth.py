"""Authentication and authorization dependencies for the Kontext API."""

import json
import logging
from collections.abc import Awaitable, Callable
from enum import StrEnum
from importlib import resources
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from kontext.auth import AuthManager, JwtValidationError, JwtValidator
from kontext.common.config import get_config
from kontext.common.jobs.trigger_actor import system_actor, user_actor
from kontext.project import ProjectService
from kontext.project.local_data import load_local_project_model
from kontext.runtime.local.auth import (
    build_local_user_with_roles,
    get_local_permission_claims,
)
from kontext.runtime.profiles import get_runtime_profile
from kontext.schema import (
    ProjectFeature,
    ProjectModel,
    TriggerActorModel,
    UserType,
    UserWithRolesModel,
)

logger = logging.getLogger(__name__)


def _is_local_mode() -> bool:
    """Return True when the server is running in local (lakehouse) mode."""
    return get_runtime_profile().is_local


# HTTP Bearer authentication scheme (optional - allows None for cookie auth)
security = HTTPBearer(auto_error=False)
# Use a module-level singleton for dependency default to satisfy linters
AUTH_CREDENTIALS = Depends(security)


def _load_permission_to_roles() -> dict[str, set[str]]:
    try:
        env_path = get_config().permission_map_path
        if env_path:
            path = Path(env_path).expanduser().resolve()
            raw_text = path.read_text(encoding="utf-8")
        else:
            resource_path = resources.files("kontext.auth.resources").joinpath(
                "security/project-permission-to-roles.json"
            )
            raw_text = resource_path.read_text(encoding="utf-8")

        raw = json.loads(raw_text)
        if not isinstance(raw, dict):
            raise RuntimeError("Invalid project permission mapping (expected JSON object).")

        loaded: dict[str, set[str]] = {}
        for permission, roles in raw.items():
            if not isinstance(permission, str) or not isinstance(roles, list):
                continue
            normalized_roles = {str(r).strip().lower() for r in roles if str(r).strip()}
            if normalized_roles:
                loaded[permission] = normalized_roles

        if not loaded:
            raise RuntimeError("Project permission mapping was empty after parsing.")

        return loaded
    except Exception as e:
        raise RuntimeError(f"Failed to load project permission map: {e}") from e


# Permission -> allowed project roles (shared mapping; fallback for safety)
PERMISSION_TO_ROLES: dict[str, set[str]] = _load_permission_to_roles()


class AccessScope(StrEnum):
    """Defines the scope of access granted to a user."""

    PROJECT = "project"  # Full access to all resources in the project
    OWNER = "owner"  # Access restricted to resources owned by the user


class AuthContext[T]:
    """Authentication and authorization context for a request."""

    user: UserWithRolesModel | None
    project: ProjectModel | None
    auth_manager: AuthManager | None
    resource: T | None
    scope: AccessScope

    def __init__(
        self,
        user: UserWithRolesModel | None = None,
        project: ProjectModel | None = None,
        auth_manager: AuthManager | None = None,
        resource: T | None = None,
        scope: AccessScope = AccessScope.PROJECT,
    ):
        self.user = user
        self.project = project
        self.auth_manager = auth_manager
        self.resource = resource
        self.scope = scope

    @property
    def project_id(self) -> UUID:
        """Get the project ID as a UUID."""
        if not self.project:
            raise HTTPException(status_code=400, detail="Project context required")
        return UUID(str(self.project.id))

    @property
    def user_id(self) -> UUID:
        """Get the user ID as a UUID."""
        if not self.user:
            raise HTTPException(status_code=401, detail="User context required")
        return UUID(str(self.user.id))

    @property
    def user_type(self) -> UserType:
        """Get the user type."""
        if not self.user or not self.user.user_type:
            raise HTTPException(status_code=401, detail="User context required")
        return self.user.user_type

    @property
    def actor_label(self) -> str:
        """Get the actor label used for audit and trigger metadata."""
        if not self.user:
            raise HTTPException(status_code=401, detail="User context required")

        raw_user_type = getattr(self.user, "user_type", None)
        if isinstance(raw_user_type, UserType):
            actor_kind = raw_user_type.value
        elif isinstance(raw_user_type, str) and raw_user_type:
            actor_kind = raw_user_type
        else:
            actor_kind = UserType.USER.value

        return f"{actor_kind}:{self.user_id}"

    @property
    def trigger_actor(self) -> TriggerActorModel:
        """Structured actor reference used to attribute job triggers."""
        if not self.user:
            raise HTTPException(status_code=401, detail="User context required")

        raw_user_type = getattr(self.user, "user_type", None)
        if isinstance(raw_user_type, UserType):
            actor_kind = raw_user_type.value
        elif isinstance(raw_user_type, str) and raw_user_type:
            actor_kind = raw_user_type
        else:
            actor_kind = UserType.USER.value

        if actor_kind == UserType.USER.value:
            return user_actor(str(self.user_id))
        return system_actor(actor_kind)

    @property
    def effective_owner_id(self) -> UUID | None:
        """
        Returns the user's ID if access is restricted to 'OWNER' scope,
        otherwise returns None (allowing project-wide retrieval).
        """
        return self.user_id if self.scope == AccessScope.OWNER else None


async def extract_project_id(request: Request) -> UUID | None:
    """
    Extract project_id from common request locations and parse it as a UUID.

    Returns:
        The project ID as a UUID if found, else None.

    Raises:
        HTTPException: 400 if an invalid UUID string is provided
    """

    def _parse_uuid(val: str) -> UUID:
        try:
            return UUID(str(val))
        except Exception:
            raise HTTPException(
                status_code=400, detail="Invalid project_id: must be a UUID"
            ) from None

    # 1) Path parameters
    for key in ("project_id", "projectId", "project"):
        if key in request.path_params:
            return _parse_uuid(request.path_params[key])

    # 2) Query parameters
    for key in ("project_id", "projectId", "project"):
        val = request.query_params.get(key)
        if val:
            return _parse_uuid(val)

    # 3) Headers
    project_id = request.headers.get("x-project-id") or request.headers.get("X-Project-Id")
    if project_id:
        return _parse_uuid(project_id)

    # 4) Cookies
    project_id = request.cookies.get("project_id") or request.cookies.get("projectId")
    if project_id:
        return _parse_uuid(project_id)

    # 5) Form data (multipart/form-data)
    if request.method in ("POST", "PUT", "PATCH"):
        try:
            form = await request.form()
            val = form.get("project_id") or form.get("projectId")
            if val:
                return _parse_uuid(str(val))
        except HTTPException:
            raise
        except Exception as e:
            # Parsing form data failed (could be malformed multipart/form-data)
            logger.debug("Failed to parse form data when extracting project id: %s", e)

    # 6) JSON body fallback
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type or request.method in ("POST", "PUT", "PATCH"):
        try:
            body = await request.json()
            if isinstance(body, dict):
                # Check for various project ID locations in the JSON body
                project_id_sources = [
                    body.get("project_id"),
                    body.get("projectId"),
                    (body.get("project") or {}).get("id"),
                    (body.get("session") or {}).get("project_id"),
                    (body.get("params") or {}).get("project_id"),
                ]
                val = next((v for v in project_id_sources if v), None)
                if val:
                    return _parse_uuid(val)
        except Exception as e:
            logger.debug("Failed to parse JSON body when extracting project id: %s", e)

    return None


def _normalize_id_for_compare(val: object | None) -> str | None:
    """Normalize an ID value for safe comparisons.

    Tries to parse UUIDs and returns a canonical lowercase string. Falls back
    to the lowercase string representation if parsing fails.
    """
    if val is None:
        return None
    try:
        return str(UUID(str(val))).lower()
    except Exception:
        return str(val).lower()


def extract_resource_ids(resource: Any) -> tuple[Any, Any]:
    """
    Extract owner_id and project_id from a resource.

    Supports Pydantic models, dataclasses, and dicts.

    Args:
        resource: The resource object or dictionary

    Returns:
        tuple: (owner_id, project_id) - values may be None
    """
    owner_id = None
    project_id = None

    # Prefer dict access (type checkers understand) and fall back to attribute access
    if isinstance(resource, dict):
        owner_id = resource.get("owner_id")
        project_id = resource.get("project_id")
    else:
        owner_id = getattr(resource, "owner_id", None)
        project_id = getattr(resource, "project_id", None)

    return owner_id, project_id


def _validate_resource_ownership(resource: Any, user_id: Any, project_id: UUID) -> None:
    """
    Validate that the user owns the resource and it belongs to the correct project.

    Raises:
        HTTPException: 403 if ownership or project validation fails.
    """
    owner_id, resource_project_id = extract_resource_ids(resource)

    # 1. Verify project mismatch
    res_proj_norm = _normalize_id_for_compare(resource_project_id)
    req_proj_norm = _normalize_id_for_compare(project_id)

    if res_proj_norm and req_proj_norm and res_proj_norm != req_proj_norm:
        logger.warning(f"Resource project mismatch: {resource_project_id} != {project_id}")
        raise HTTPException(status_code=403, detail="Access denied: Resource project mismatch")

    # 2. Verify ownership
    owner_norm = _normalize_id_for_compare(owner_id)
    user_norm = _normalize_id_for_compare(user_id)

    if not owner_norm or owner_norm != user_norm:
        logger.warning(f"User {user_id} is not the owner of the resource {owner_id}")
        raise HTTPException(status_code=403, detail="Access denied: Insufficient permissions")

    logger.info(f"User {user_id} is the owner of the resource, allowing access")


def check_project_features(project: ProjectModel, required_features: list[ProjectFeature]) -> None:
    """
    Check if a project has all required features enabled.

    Args:
        project: The project to check
        required_features: List of features that must be enabled

    Raises:
        HTTPException: 403 if any required feature is missing
    """
    if not project.configuration or not project.configuration.features:
        logger.warning(f"Project {project.id} has no features configured")
        raise HTTPException(status_code=403, detail="Project features not configured")

    project_features = project.configuration.features
    missing_features = [f.value for f in required_features if f not in project_features]

    if missing_features:
        logger.warning(f"Feature check failed for project {project.id}: missing {missing_features}")
        raise HTTPException(
            status_code=403,
            detail=(f"Required project features not enabled: {', '.join(missing_features)}"),
        )


def check_user_permissions(
    user: UserWithRolesModel, project_id: UUID | None, required_permissions: list[str]
) -> bool:
    """
    Check if a user has any of the required permissions for a project.

    New model:
    1. Check system-wide permission claim (e.g., "querysessions.execute")
    2. For project scope, derive effective permission from project roles
       (e.g., Project.Owner / Project.Admin) rather than from scoped permission claims.

    Args:
        user: The user to check
        project_id: The project ID to check permissions against (UUID), or None
        required_permissions: List of permissions to check

    Returns:
        True if the user has at least one of the required permissions
    """
    permission_claims = user.permission_claims or []

    # Normalize project roles lookup to the dict shape expected by auth responses.
    # {project_id: [role_types]}
    project_roles = user.project_roles or {}
    project_id_key = str(project_id).lower() if project_id else None
    roles_for_project = (
        [r.lower() for r in project_roles.get(project_id_key, [])] if project_id_key else []
    )

    for permission in required_permissions:
        # 1. Check system-wide permission
        if permission in permission_claims:
            return True

        # 2. For project scope, derive from project roles
        if project_id_key:
            allowed_roles = PERMISSION_TO_ROLES.get(permission)
            if allowed_roles and any(r in allowed_roles for r in roles_for_project):
                return True

    return False


# ── Local-mode auth helpers ──────────────────────────────────────────────────


def _get_local_user() -> UserWithRolesModel | None:
    """Read the ambient local user profile as ``UserWithRolesModel``."""
    from kontext.account import read_profile

    profile = read_profile()
    if profile is None:
        return None
    return build_local_user_with_roles(profile)


async def resolve_local_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> UserWithRolesModel | None:
    """Single policy for local identity resolution (see local_auth).

    Returns the identity as ``UserWithRolesModel`` for context building.
    """
    from .local_auth import profile_to_model
    from .local_auth import resolve_local_user as resolve

    profile = await resolve(request, credentials)
    return None if profile is None else profile_to_model(profile)


def _load_local_project(project_id: UUID) -> ProjectModel | None:
    """Load a ``ProjectModel`` from the local SQLite database by ID."""
    return load_local_project_model(project_id)


def _all_local_permissions() -> list[str]:
    """Return a generous permission set for local mode."""
    return get_local_permission_claims()


async def get_auth_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = AUTH_CREDENTIALS,
) -> AuthContext:
    """
    Extract authentication context from request headers (Bearer token or cookies).

    In local mode (``KONTEXT_LOCAL_MODE=true``), reads the user profile from
    the lake directory instead of validating a JWT.

    Args:
        request: FastAPI Request object
        credentials: HTTP Bearer credentials from the request (optional)

    Returns:
        AuthContext with user information

    Raises:
        HTTPException: 401 if authentication fails or is missing
    """
    # ── Local mode: one shared identity policy ──────────────────────────
    if _is_local_mode():
        profile = await resolve_local_user(request, credentials)
        user = build_local_user_with_roles(profile) if profile is not None else None
        if user is None:
            # First-launch: minimal anonymous context.
            return AuthContext(scope=AccessScope.PROJECT)

        auth_context: AuthContext = AuthContext(user=user, scope=AccessScope.PROJECT)

        # Attach project context if project_id is present in the request
        project_id = await extract_project_id(request)
        if project_id:
            project = _load_local_project(project_id)
            if project:
                auth_context.project = project
                user.permission_claims = _all_local_permissions()
                if str(project.owner_id) == str(user.id):
                    user.project_roles = {
                        **(user.project_roles or {}),
                        str(project_id): ["owner"],
                    }

        return auth_context

    # ── Cloud mode: JWT validation ───────────────────────────────────────

    # Check if distributed JWT validation is available
    jwt_secret_key = get_config().jwt_secret_key
    use_distributed_validation = bool(jwt_secret_key)

    # Extract Bearer token from Authorization header
    auth_header = None
    for header_name, header_value in request.headers.items():
        if header_name.lower() == "authorization":
            auth_header = header_value
            break

    # Try distributed JWT validation first if conditions are met
    if auth_header and auth_header.startswith("Bearer ") and use_distributed_validation:
        access_token = auth_header[7:]  # Remove "Bearer " prefix

        # Use distributed JWT validation (no API call required)
        try:
            validator = JwtValidator.from_environment()
            jwt_claims = validator.validate_token(access_token)

            logger.info(f"Authenticated user via distributed JWT validation: {jwt_claims.user_id}")

            # Create a minimal user object from JWT claims
            from kontext.auth.authentication.jwt_utils import JwtUserExtractor

            user = JwtUserExtractor.extract_user(jwt_claims)

            # Create a minimal AuthManager for API calls
            from kontext.auth import TokenAuth, TokenAuthConfig

            api_url = get_config().internal_api_url or "http://localhost:8101"
            config = TokenAuthConfig.from_tokens(access_token, api_base_url=api_url)
            auth = TokenAuth(config)
            auth_manager = AuthManager(auth)

            return AuthContext(user=user, project=None, auth_manager=auth_manager)

        except JwtValidationError:
            # Let the app-level exception handler format a consistent RFC7807 response
            # (including a distinct problem 'type' for unsupported token versions).
            raise
        except Exception as e:
            logger.error(f"Distributed JWT validation error: {e}", exc_info=True)
            raise HTTPException(
                status_code=401,
                detail="Authentication failed due to an internal error.",
            ) from e

    if not use_distributed_validation:
        logger.error("JWT_SECRET_KEY not configured. API authentication is disabled.")
        raise HTTPException(
            status_code=500,
            detail="API authentication is misconfigured. Please contact administrator.",
        )

    raise HTTPException(
        status_code=401,
        detail="Please provide a valid Bearer token in the Authorization header.",
    )


def require_project_authorization[T](
    required_features: list[ProjectFeature] | None = None,
    required_permissions: list[str] | None = None,
    resource_getter: (Callable[[Request, AuthContext[T]], Awaitable[T | None]] | None) = None,
    allow_owner: bool = False,
    require_project: bool = True,
):
    """
    Create a dependency that enforces project-level authorization using permissions.
    """

    # Use module-level singleton for dependency to satisfy linters
    AUTH_CTX = Depends(get_auth_context)

    async def check_authorization(
        request: Request, auth_context: AuthContext[T] = AUTH_CTX
    ) -> AuthContext[T]:
        """
        Validate project authorization for the authenticated user.
        """
        # User authentication already validated by get_auth_context
        user = auth_context.user
        auth_manager = auth_context.auth_manager
        local_mode = _is_local_mode()

        # Validate that auth_manager and user are present
        if user is None and required_permissions:
            raise HTTPException(status_code=401, detail="Authentication required")

        if not local_mode and (not auth_manager or not user):
            raise HTTPException(status_code=500, detail="Invalid authentication context")

        # Extract project_id from common locations
        project_id = await extract_project_id(request)

        # Get project context if project_id is provided
        if not project_id:
            if require_project:
                raise HTTPException(
                    status_code=400, detail="Project context required but not provided"
                )

            # If project is not required, we still check permissions if provided
            if required_permissions:
                assert user is not None  # guarded by the user is None check above
                if not check_user_permissions(user, None, required_permissions):
                    raise HTTPException(
                        status_code=403,
                        detail="Access denied: Insufficient permissions",
                    )

            return auth_context

        try:
            # In local mode the project is already attached by get_auth_context
            project = auth_context.project

            if not project:
                if local_mode:
                    project = _load_local_project(project_id)
                else:
                    # Fetch project from local database using service
                    local_project_service = ProjectService(project_id=project_id)
                    project = await local_project_service.get_project_async()

                if not project:
                    if require_project:
                        raise HTTPException(
                            status_code=404, detail=f"Project {project_id} not found"
                        )

                    logger.info(
                        "Project %s not found in the store. Continuing "
                        "without project context because require_project is false.",
                        project_id,
                    )

            if project:
                auth_context.project = project
                logger.info(f"Found project: {project.id} ({project.project_name})")

            # Fetch resource if getter is provided
            if resource_getter:
                auth_context.resource = await resource_getter(request, auth_context)

            # Check project features if required
            if project and required_features:
                check_project_features(project, required_features)

            # Project-level access requires a resolved user
            if user is None:
                raise HTTPException(status_code=401, detail="Authentication required")

            # Check user permissions
            has_permission = True
            if required_permissions:
                has_permission = check_user_permissions(user, project_id, required_permissions)

            # 1. If user has permissions, allow PROJECT scope access
            if has_permission:
                logger.info(f"Authorization successful for user {user.id} on project {project_id}")
                auth_context.scope = AccessScope.PROJECT
                return auth_context

            # 2. If user lacks permissions, check if they own the resource (if allowed)
            if not allow_owner:
                logger.warning(
                    f"User {user.id} lacks permissions on project {project_id} "
                    "and owner access is not allowed"
                )
                raise HTTPException(
                    status_code=403, detail="Access denied: Insufficient permissions"
                )

            # If we are here, allow_owner is True and user lacks project permissions
            if auth_context.resource:
                # Validate ownership of the specific resource
                _validate_resource_ownership(auth_context.resource, user.id, project_id)
                auth_context.scope = AccessScope.OWNER
                return auth_context
            else:
                # For LIST operations (no resource fetched yet),
                # allow access but restrict scope to OWNER
                logger.info(
                    f"User {user.id} lacks project permissions, restricting access to OWNER scope"
                )
                auth_context.scope = AccessScope.OWNER
                return auth_context

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Authorization check failed: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail="Authorization check failed") from e

    return check_authorization


def create_auth_dependency[T](
    required_features: list[ProjectFeature] | None = None,
    required_permissions: list[str] | None = None,
    resource_getter: (Callable[[Request, AuthContext[T]], Awaitable[T | None]] | None) = None,
    allow_owner: bool = False,
    require_project: bool = True,
):
    """Create a FastAPI authorization dependency."""
    return Depends(
        require_project_authorization(
            required_features=required_features,
            required_permissions=required_permissions,
            resource_getter=resource_getter,
            allow_owner=allow_owner,
            require_project=require_project,
        )
    )


def get_user_id[T](auth_context: AuthContext[T]) -> str | None:
    """Extract user ID from auth context."""
    return str(auth_context.user.id) if auth_context.user else None


def get_user_id_as_uuid[T](auth_context: AuthContext[T]) -> UUID | None:
    """Extract user ID from auth context as UUID."""
    return UUID(str(auth_context.user.id)) if auth_context.user else None


def get_project_name[T](auth_context: AuthContext[T]) -> str | None:
    """Extract project name from auth context."""
    return auth_context.project.project_name if auth_context.project else None
