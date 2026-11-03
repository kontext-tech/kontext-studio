"""Configuration helpers for the local runtime profile."""

from __future__ import annotations

import os
from pathlib import Path

from kontext.common import LOCAL_DEFAULT_SITE_FEATURES
from kontext.common.config import get_config, provide_config
from kontext.project.local import (
    LOCAL_PROJECT_ACCESS_LEVEL,
    LOCAL_PROJECT_CODE,
    LOCAL_PROJECT_DESCRIPTION,
    LOCAL_PROJECT_NAME,
    get_default_local_file_types,
    get_default_local_project_configuration,
    get_default_local_project_configuration_payload,
)
from kontext.schema import SiteConfigResponse

LOCAL_SITE_FEATURES = sorted(feature.value for feature in LOCAL_DEFAULT_SITE_FEATURES)
LOCAL_DEFAULT_USER_EMAIL = "local@kontext.local"
LOCAL_DEFAULT_USER_PASSWORD = "Loc@l12e456"
LOCAL_DEFAULT_USER_FIRST_NAME = "Local"
LOCAL_DEFAULT_USER_LAST_NAME = "Admin"
LOCAL_ACCESS_TOKEN_TTL_SECONDS = 30 * 24 * 60 * 60
LOCAL_REFRESH_TOKEN_TTL_SECONDS = 365 * 24 * 60 * 60

# The default local project configuration is owned by ``kontext.project.local``;
# re-export it here so local-runtime consumers keep a single import surface.
__all__ = [
    "LOCAL_ACCESS_TOKEN_TTL_SECONDS",
    "LOCAL_DEFAULT_USER_EMAIL",
    "LOCAL_DEFAULT_USER_FIRST_NAME",
    "LOCAL_DEFAULT_USER_LAST_NAME",
    "LOCAL_DEFAULT_USER_PASSWORD",
    "LOCAL_PROJECT_ACCESS_LEVEL",
    "LOCAL_PROJECT_CODE",
    "LOCAL_PROJECT_DESCRIPTION",
    "LOCAL_PROJECT_NAME",
    "LOCAL_REFRESH_TOKEN_TTL_SECONDS",
    "LOCAL_SITE_FEATURES",
    "configure_local_database_url",
    "configure_local_runtime",
    "get_default_local_file_types",
    "get_default_local_project_configuration",
    "get_default_local_project_configuration_payload",
    "get_local_access_token_ttl_seconds",
    "get_local_data_dir",
    "get_local_database_url",
    "get_local_default_user_email",
    "get_local_default_user_password",
    "get_local_refresh_token_ttl_seconds",
    "get_local_site_config",
    "is_local_mode",
]


def is_local_mode() -> bool:
    """Return ``True`` when local mode is enabled.

    Reads the canonical ``KONTEXT_LOCAL_MODE`` setting (``KontextConfig``),
    which still resolves the raw environment variable at settings-creation
    time.
    """
    return get_config().local_mode


def get_local_data_dir() -> Path:
    """Return the local Kontext data directory, creating it if needed."""
    data_dir = Path.home() / ".kontext"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


def get_local_database_url() -> str:
    """Return the SQLite connection string used for local mode."""
    return f"sqlite:///{get_local_data_dir() / 'kontext.db'}"


def configure_local_database_url() -> str:
    """Seed the cross-process project database URL and return it.

    The environment seed is the *transport* to spawned worker and runner
    processes; in-process readers resolve the same value through settings
    (``KONTEXT_PROJECT_DB_URL`` / legacy ``PROJECT_DB_URL``).
    """
    db_url = get_local_database_url()
    os.environ["PROJECT_DB_URL"] = db_url
    return db_url


def configure_local_runtime(*, log_level: str | None = None, log_format: str | None = None) -> str:
    """Configure the local runtime settings and environment contract.

    In-process JWT and logging values are provided through the settings
    singleton (:func:`kontext.common.provide_config`) — deep layers read
    settings, never ``os.environ``. Only the documented *cross-process*
    values are seeded into the environment, because spawned worker and
    kernel-runner processes reconstruct their settings from the inherited
    environment at startup:

    - ``PROJECT_DB_URL``: the project database URL used by every process
      touching the project database.
    - ``KONTEXT_LOCAL_MODE``: the deployment-profile flag.
    """
    from .auth import get_local_jwt_secret

    os.environ.setdefault("KONTEXT_LOCAL_MODE", "true")

    db_url = configure_local_database_url()

    overrides: dict[str, str] = {}
    if not (os.getenv("KONTEXT_JWT_SECRET_KEY") or os.getenv("JWT_SECRET_KEY")):
        overrides["jwt_secret_key"] = get_local_jwt_secret()
    if not (os.getenv("KONTEXT_JWT_ISSUER") or os.getenv("JWT_ISSUER")):
        overrides["jwt_issuer"] = "kontext-local"
    if not (os.getenv("KONTEXT_JWT_AUDIENCE") or os.getenv("JWT_AUDIENCE")):
        overrides["jwt_audience"] = "kontext-platform"
    if log_level and not (os.getenv("KONTEXT_LOG_LEVEL") or os.getenv("LOG_LEVEL")):
        overrides["log_level"] = log_level
    if log_format and not (os.getenv("KONTEXT_LOG_FORMAT") or os.getenv("LOG_FORMAT")):
        overrides["log_format"] = log_format
    if overrides:
        provide_config(**overrides)

    return db_url


def get_local_site_config() -> SiteConfigResponse:
    """Return the site configuration for local mode."""
    return SiteConfigResponse(
        site_name="Kontext (Local)",
        default_project_code=LOCAL_PROJECT_CODE,
        auth_enabled=True,
        registration_enabled=False,
        features=LOCAL_SITE_FEATURES,
        setup_url=None,
    )


def get_local_default_user_email() -> str:
    return os.getenv("KONTEXT_LOCAL_DEFAULT_USER_EMAIL", LOCAL_DEFAULT_USER_EMAIL)


def get_local_default_user_password() -> str:
    return os.getenv("KONTEXT_LOCAL_DEFAULT_USER_PASSWORD", LOCAL_DEFAULT_USER_PASSWORD)


def get_local_access_token_ttl_seconds() -> int:
    value = os.getenv("KONTEXT_LOCAL_ACCESS_TOKEN_TTL_SECONDS")
    return int(value) if value else LOCAL_ACCESS_TOKEN_TTL_SECONDS


def get_local_refresh_token_ttl_seconds() -> int:
    value = os.getenv("KONTEXT_LOCAL_REFRESH_TOKEN_TTL_SECONDS")
    return int(value) if value else LOCAL_REFRESH_TOKEN_TTL_SECONDS
