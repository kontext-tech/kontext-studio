"""Permission constants for Kontext.

All permission claim values are lowercase strings shared with the API contract.
"""


class FilePermissions:
    """File permission claim values.

    Note: The actual claim values use 'resources.*' for backward
    compatibility with existing tokens and .NET API claims.
    """

    CREATE = "resources.create"
    READ = "resources.read"
    UPDATE = "resources.update"
    DELETE = "resources.delete"


class JobPermissions:
    """Job permission claim values."""

    CREATE = "jobs.create"
    READ = "jobs.read"
    UPDATE = "jobs.update"
    DELETE = "jobs.delete"
    EXECUTE = "jobs.execute"


class ProjectPermissions:
    """Project permission claim values."""

    CREATE = "projects.create"
    READ = "projects.read"
    UPDATE = "projects.update"
    DELETE = "projects.delete"


class EventPermissions:
    """Event permission claim values."""

    CREATE = "events.create"
    READ = "events.read"


class QuerySessionPermissions:
    """Query session permission claim values."""

    CREATE = "querysessions.create"
    READ = "querysessions.read"
    UPDATE = "querysessions.update"
    DELETE = "querysessions.delete"
    EXECUTE = "querysessions.execute"


class ChatSessionPermissions:
    """Chat session permission claim values."""

    CREATE = "chatsessions.create"
    READ = "chatsessions.read"
    UPDATE = "chatsessions.update"
    DELETE = "chatsessions.delete"
