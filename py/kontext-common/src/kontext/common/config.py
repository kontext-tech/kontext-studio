"""Centralised runtime configuration for Kontext.

``KontextConfig`` is a Pydantic *Settings* model that reads values from
(highest priority first):

1. Environment variables (prefix ``KONTEXT_``).
2. An optional ``.env`` file in the working directory.
3. An optional ``.kontext/config.toml`` file (TOML section ``[kontext]``).

Create the singleton via :func:`get_config`.  Subsystems should import
and query this object instead of reading ``os.environ`` directly.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any, Literal

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# ── TOML loader ──────────────────────────────────────────────────────────────

_TOML_PATH = Path(".kontext") / "config.toml"


def _load_toml_settings() -> dict[str, Any]:
    """Read settings from ``.kontext/config.toml`` if it exists.

    The TOML file is expected to have a ``[kontext]`` section whose keys
    map 1-to-1 to :class:`KontextConfig` fields::

        [kontext]
        lake_path = "/data/lake"
        port = 9000
    """
    if not _TOML_PATH.is_file():
        return {}
    try:
        data = tomllib.loads(_TOML_PATH.read_text(encoding="utf-8"))
        return dict(data.get("kontext", {}))
    except Exception:
        return {}


class KontextConfig(BaseSettings):
    """Single source of truth for all runtime settings.

    Fields below also accept their legacy, unprefixed environment-variable
    names (``PROJECT_DB_URL``, ``JWT_*``, ``LOG_*``) via ``AliasChoices`` so
    existing deployments keep working; the canonical name is the
    ``KONTEXT_``-prefixed spelling.
    """

    model_config = SettingsConfigDict(
        env_prefix="KONTEXT_",
        # Order matters: pydantic-settings merges the tuple in order and the
        # *last* file wins, so `.env.local` must come second to override `.env`.
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: Any,
        env_settings: Any,
        dotenv_settings: Any,
        file_secret_settings: Any,
    ) -> tuple[Any, ...]:
        """Insert TOML as the lowest-priority settings source."""
        from pydantic_settings import InitSettingsSource

        toml_source = InitSettingsSource(settings_cls, init_kwargs=_load_toml_settings())
        if _TEST_ISOLATION:
            # Test isolation: skip the TOML config file as well, mirroring the
            # ``_env_file=None`` treatment of dotenv files in ``get_config``.
            toml_source = InitSettingsSource(settings_cls, init_kwargs={})
        # Order: init > env > .env > TOML > file-secrets
        return (
            init_settings,
            env_settings,
            dotenv_settings,
            toml_source,
            file_secret_settings,
        )

    # ── Core paths ───────────────────────────────────────────────────────
    lake_path: Path = Field(
        default=Path(".kontext"), description="Root directory of the local data lake."
    )
    local_storage_path: str = Field(
        default="",
        description="Root for local file storage (DuckDB, secrets). "
        "Falls back to ``~/.kontext/storage``.",
    )

    # ── Server ───────────────────────────────────────────────────────────
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000)

    # ── Logging / telemetry ──────────────────────────────────────────────
    log_level: str = Field(
        default="INFO",
        validation_alias=AliasChoices("KONTEXT_LOG_LEVEL", "LOG_LEVEL"),
        description="Root log level (DEBUG, INFO, WARNING, ERROR).",
    )
    log_format: Literal["json", "plain"] = Field(
        default="json",
        validation_alias=AliasChoices("KONTEXT_LOG_FORMAT", "LOG_FORMAT"),
        description="Log output format.",
    )
    otel_enabled: bool = Field(
        default=False,
        description="Enable OpenTelemetry export (requires optional dep).",
    )

    # ── LLM / AI ─────────────────────────────────────────────────────────
    model_provider: str = Field(
        default="lm_studio",
        description=(
            "Default LLM provider (lm_studio, ollama, openai, anthropic, "
            "openrouter, openai_compatible, gemini, bedrock)."
        ),
    )

    # ── Mode flags ───────────────────────────────────────────────────────
    local_mode: bool = Field(
        default=False, description="When True the platform runs against the local lake."
    )

    # ── Data / auth (legacy names accepted via aliases) ──────────────────
    project_db_url: str = Field(
        default="",
        validation_alias=AliasChoices("KONTEXT_PROJECT_DB_URL", "PROJECT_DB_URL"),
        description=(
            "SQLAlchemy connection URL for the project database "
            "(SQLite locally, PostgreSQL in hosted deployments)."
        ),
    )
    jwt_secret_key: str = Field(
        default="",
        validation_alias=AliasChoices("KONTEXT_JWT_SECRET_KEY", "JWT_SECRET_KEY"),
        description="Secret key for JWT token signing and validation.",
    )
    jwt_issuer: str = Field(
        default="kontext-api",
        validation_alias=AliasChoices("KONTEXT_JWT_ISSUER", "JWT_ISSUER"),
        description="Expected JWT issuer.",
    )
    jwt_audience: str = Field(
        default="kontext-platform",
        validation_alias=AliasChoices("KONTEXT_JWT_AUDIENCE", "JWT_AUDIENCE"),
        description="Expected JWT audience.",
    )

    # ── Operational overrides (deployment-specific) ─────────────────────
    internal_api_url: str = Field(
        default="",
        validation_alias=AliasChoices("KONTEXT_INTERNAL_API_URL", "INTERNAL_KONTEXT_API_URL"),
        description=(
            "Base URL the API uses to call itself (or a peer) for internal "
            "auth flows. Falls back to http://localhost:8101 in code."
        ),
    )
    permission_map_path: str = Field(
        default="",
        validation_alias=AliasChoices(
            "KONTEXT_PROJECT_PERMISSION_MAP_PATH", "PROJECT_PERMISSION_MAP_PATH"
        ),
        description=(
            "Optional override file for the project permission-to-roles map "
            "(defaults to the bundled security resource)."
        ),
    )


# ── Singleton accessor ───────────────────────────────────────────────────────

_config: KontextConfig | None = None

# Test isolation: when enabled, new settings instances ignore ``.env`` files
# and the TOML source, so tests are deterministic on any developer machine
# (configuration comes purely from the OS environment). Production is
# unaffected: the flag defaults to False.
_TEST_ISOLATION = False


def enable_test_isolation() -> None:
    """Make settings reads in this process test-deterministic.

    New instances created after this call read only the OS environment. Call
    :func:`reset_config` afterwards so the first lazy ``get_config()`` picks
    the mode up.
    """
    global _TEST_ISOLATION
    _TEST_ISOLATION = True


def get_config() -> KontextConfig:
    """Return (or create) the global ``KontextConfig`` singleton."""
    global _config
    if _config is None:
        _config = (
            KontextConfig(_env_file=None)  # type: ignore[call-arg]
            if _TEST_ISOLATION
            else KontextConfig()
        )
    return _config


def provide_config(**overrides: Any) -> KontextConfig:
    """Create the settings singleton with composition-time overrides.

    Composition roots (``configure_local_runtime``, deployment entrypoints)
    call this *before* any consumer reads :func:`get_config`. Override values
    are applied at init priority (highest); every other field still resolves
    from environment, ``.env``, and ``config.toml`` as usual.
    """
    global _config
    _config = KontextConfig(**overrides)  # type: ignore[call-arg]
    return _config


def reset_config() -> None:
    """Clear the singleton — mainly useful in tests."""
    global _config
    _config = None
