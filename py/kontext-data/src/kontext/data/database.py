"""Database utilities for the project database.

This module provides shared database infrastructure for all project data
using a single project database with project_id partitioning.

Architecture:
    - One project database shared by all projects
    - All tables include a required `project_id` column (tenant key)
    - Migrations run once at startup with advisory locking

Backends:
    The dialect is chosen by the PROJECT_DB_URL connection string. Local mode
    uses SQLite; a PostgreSQL URL (via psycopg) is also supported. Harness
    session state lives in this same project database (the `SessionPersistence`
    tables); the former per-project Agno SQLite file is retired.

Concurrency:
    The connection pool is managed by SQLAlchemy and configured per the
    PROJECT_DB_URL connection string.
"""

import contextlib
import logging
from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import QueuePool

from kontext.common.config import get_config
from kontext.common.constants.env_vars import DatabaseEnvVars

# Shared declarative base for all project tables
Base = declarative_base()

logger = logging.getLogger(__name__)

# We rely on function-level caching (lru_cache) instead of module-level globals


def get_project_database_url() -> str:
    """Get the project database URL from settings.

    Reads ``KONTEXT_PROJECT_DB_URL`` (or the legacy ``PROJECT_DB_URL`` name)
    through the settings singleton so deep layers never touch ``os.environ``
    directly.

    Returns:
        SQLAlchemy connection URL (SQLite locally, or PostgreSQL via psycopg)

    Raises:
        ValueError: If the project database URL is not configured
    """
    url = get_config().project_db_url
    if not url:
        raise ValueError(
            f"{DatabaseEnvVars.PROJECT_DATABASE_URL} environment variable is not set. "
            "Cannot connect to project database."
        )
    return url


@lru_cache(maxsize=1)
def get_engine():
    """Get the singleton SQLAlchemy engine for the project database.

    Configures connection pooling and connection parameters for the dialect
    selected by PROJECT_DB_URL. The engine is created once and cached for the
    lifetime of the application.

    Returns:
        SQLAlchemy engine instance

    Raises:
        ValueError: If PROJECT_DATABASE_URL is not configured
    """
    database_url = get_project_database_url()

    # Configure connection parameters based on dialect
    connect_args = {}
    pool_args = {
        "pool_recycle": 3600,
        "pool_pre_ping": True,
        "echo": False,
    }

    if database_url.startswith("sqlite"):
        from sqlalchemy.pool import NullPool

        pool_args["poolclass"] = NullPool
        # ``timeout`` is SQLite's busy timeout in seconds: without it a writer
        # that collides with the API process returns "database is locked"
        # immediately. Local mode runs the API and the job worker as separate
        # processes on the same file, so this is required for correctness.
        connect_args["timeout"] = 30.0
        connect_args["check_same_thread"] = False
        pool_args["execution_options"] = {"schema_translate_map": {"project": None}}
    else:
        pool_args.update(
            {
                "poolclass": QueuePool,
                "pool_size": 5,
                "max_overflow": 10,
                "pool_timeout": 30,
            }
        )

    engine = create_engine(database_url, connect_args=connect_args, **pool_args)

    if database_url.startswith("sqlite"):
        _enable_sqlite_wal(engine)

    logger.info(
        "Created project database engine: %s",
        database_url.split("@")[-1] if "@" in database_url else "localhost",
    )

    return engine


def _enable_sqlite_wal(engine) -> None:
    """Put SQLite connections in WAL mode for multi-process access.

    The local API and the local job worker are separate processes sharing one
    ``kontext.db`` file. WAL lets readers proceed while a writer is active and
    greatly reduces ``database is locked`` errors. ``synchronous=NORMAL`` is
    the recommended pairing with WAL.
    """
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragmas(dbapi_connection, _record) -> None:
        with contextlib.suppress(Exception):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()


@lru_cache(maxsize=1)
def get_session_factory():
    """Get the session factory for the project database.

    Returns:
        SQLAlchemy sessionmaker

    Raises:
        ValueError: If PROJECT_DATABASE_URL is not configured
    """
    engine = get_engine()
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    logger.debug("Created session factory for project database")

    return factory


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for getting a database session.

    Usage:
        @router.get("/items")
        def get_items(
            project_id: str,
            db: Session = Depends(get_db)
        ):
            return db.query(Item).filter(Item.project_id == project_id).all()

    Yields:
        Database session
    """
    SessionFactory = get_session_factory()
    db = SessionFactory()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_sync_db_session() -> Generator[Session, None, None]:
    """Context manager for sync database sessions.

    This is the preferred pattern for database operations in async code.
    Use with asyncio.to_thread() to avoid blocking.

    Usage:
        async def get_data():
            def _sync_query():
                with get_sync_db_session() as session:
                    service = FileDataService(session)
                    return service.get_files_for_project(project_id)
                    # session commits/rollsback automatically

            return await asyncio.to_thread(_sync_query)

    Yields:
        Sync database session that will be closed after use
    """
    SessionFactory = get_session_factory()
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


def get_sync_session_for_project(project_id: str) -> Session:
    """Get a database session (legacy compatibility - project_id is ignored).

    The project_id parameter is ignored; all projects use the same project database.

    Args:
        project_id: Ignored (kept for backward compatibility)

    Returns:
        Session: A SQLAlchemy session connected to the project database.
    """
    # Use the cached session factory for consistency with other helpers
    return get_session_factory()()


def check_database_connectivity() -> tuple[bool, str | None]:
    """Probe the project database with a trivial query.

    Keeps SQLAlchemy details inside ``kontext-data`` so transport layers do not
    depend on the driver directly.

    Returns:
        Tuple of (is_connected, error_message).
    """
    try:
        from sqlalchemy import text

        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, None
    except Exception as e:
        logger.warning("Database connectivity check failed: %s", e)
        return False, f"Database error: {e!s}"
