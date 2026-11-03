"""
FastAPI dependencies for the Kontext API.
"""

from .auth import (
    AccessScope,
    AuthContext,
    create_auth_dependency,
    get_auth_context,
    get_project_name,
    get_user_id,
    get_user_id_as_uuid,
    require_project_authorization,
)
from .jobs import QUEUE_CLIENT_DEP, get_queue_client
from .params import (
    BLOCK_ID_PATH,
    CHAT_SESSION_ID_PATH,
    CONNECTION_ID_PATH,
    ENTITY_ID_PATH,
    FILE_ID_PATH,
    FILTER_QUERY,
    JOB_ID_PATH,
    JOB_TYPE_PATH,
    LIMIT_QUERY,
    MY_OWNED_ONLY_QUERY,
    PAGE_INDEX_QUERY,
    PAGE_SIZE_QUERY,
    PROJECT_CODE_PATH,
    PROJECT_ID_PATH,
    PROJECT_ID_QUERY,
    RUN_ID_PATH,
    SESSION_ID_PATH,
)
from .site_features import require_site_feature
from .utils import (
    ensure_uuid_param,
    extract_path_param,
    get_client_ip,
    parse_uuid_param,
)

__all__ = [
    "BLOCK_ID_PATH",
    "CHAT_SESSION_ID_PATH",
    "CONNECTION_ID_PATH",
    "ENTITY_ID_PATH",
    "FILE_ID_PATH",
    "FILTER_QUERY",
    "JOB_ID_PATH",
    "JOB_TYPE_PATH",
    "LIMIT_QUERY",
    "MY_OWNED_ONLY_QUERY",
    "PAGE_INDEX_QUERY",
    "PAGE_SIZE_QUERY",
    "PROJECT_CODE_PATH",
    "PROJECT_ID_PATH",
    "PROJECT_ID_QUERY",
    "QUEUE_CLIENT_DEP",
    "RUN_ID_PATH",
    "SESSION_ID_PATH",
    "AccessScope",
    "AuthContext",
    "create_auth_dependency",
    "ensure_uuid_param",
    "extract_path_param",
    "get_auth_context",
    "get_client_ip",
    "get_project_name",
    "get_queue_client",
    "get_user_id",
    "get_user_id_as_uuid",
    "parse_uuid_param",
    "require_project_authorization",
    "require_site_feature",
]
