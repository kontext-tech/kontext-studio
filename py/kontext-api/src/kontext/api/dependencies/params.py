"""Common query and path parameter definitions for the Kontext API.

The public API (and therefore the generated SDKs) uses camelCase for query and
path parameter names, while Python handlers keep snake_case arguments. Each
parameter below declares its camelCase name explicitly via ``alias``.

Query parameters are reusable :data:`~typing.Annotated` aliases rather than
shared ``Query()`` default values. FastAPI writes the resolved type onto a
``FieldInfo`` used as a default in place, so sharing one ``Query()`` instance
across handlers would let the last-registered route mutate the others' schema.
``Annotated`` metadata is copied per parameter instead, which keeps the shared
definitions immutable. The default value lives at the signature (``= ...``),
not inside the ``Query`` call.
"""

from typing import Annotated
from uuid import UUID

from fastapi import Path, Query

# ---------------------------------------------------------------------------
# Shared query parameters
# ---------------------------------------------------------------------------

PROJECT_ID_QUERY = Annotated[
    UUID, Query(alias="projectId", description="Project ID for authorization")
]
MY_OWNED_ONLY_QUERY = Annotated[
    bool,
    Query(
        alias="mySessionsOnly",
        description="Whether to return only the current user's owned resources",
    ),
]
PAGE_INDEX_QUERY = Annotated[
    int, Query(alias="pageIndex", ge=1, description="Page number (1-indexed)")
]
PAGE_SIZE_QUERY = Annotated[
    int, Query(alias="pageSize", ge=1, le=100, description="Items per page")
]
FILTER_QUERY = Annotated[str | None, Query(alias="filter", description="Filter by name or text")]
LIMIT_QUERY = Annotated[
    int, Query(alias="limit", ge=1, le=1000, description="Maximum records to return")
]

# ---------------------------------------------------------------------------
# Shared path parameters
#
# Path parameters vary in Python type across handlers (for example
# ``session_id`` is ``str`` in one router and ``UUID`` in another), so these
# stay metadata-only ``Path`` instances used inside ``Annotated[<type>, ...]``.
# ---------------------------------------------------------------------------

PROJECT_ID_PATH = Path(alias="projectId")
PROJECT_CODE_PATH = Path(alias="projectCode")
CONNECTION_ID_PATH = Path(alias="connectionId")
ENTITY_ID_PATH = Path(alias="entityId")
RUN_ID_PATH = Path(alias="runId")
JOB_ID_PATH = Path(alias="jobId")
JOB_TYPE_PATH = Path(alias="jobType")
FILE_ID_PATH = Path(alias="fileId")
BLOCK_ID_PATH = Path(alias="blockId")
CHAT_SESSION_ID_PATH = Path(alias="chatSessionId")
SESSION_ID_PATH = Path(alias="sessionId")
