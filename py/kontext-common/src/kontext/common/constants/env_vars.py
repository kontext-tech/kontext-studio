"""
Environment variable constants for the Kontext Core package.

This module centralizes all environment variable names used across the package
to ensure consistency and make maintenance easier.
"""


# Authentication Environment Variables
class AuthEnvVars:
    """Environment variables for authentication"""

    # Token Authentication (Bearer tokens)
    ACCESS_TOKEN = "KONTEXT_ACCESS_TOKEN"
    REFRESH_TOKEN = "KONTEXT_REFRESH_TOKEN"

    # Cookie Authentication
    COOKIES = "KONTEXT_COOKIES"

    # Interactive Authentication
    AUTH_CALLBACK_PORT = "KONTEXT_AUTH_CALLBACK_PORT"
    AUTH_TIMEOUT_SECONDS = "KONTEXT_AUTH_TIMEOUT_SECONDS"
    AUTH_AUTO_OPEN_BROWSER = "KONTEXT_AUTH_AUTO_OPEN_BROWSER"

    # JWT Configuration (for distributed validation)
    JWT_SECRET_KEY = "JWT_SECRET_KEY"
    JWT_ISSUER = "JWT_ISSUER"
    JWT_AUDIENCE = "JWT_AUDIENCE"

    # Canonical KONTEXT_-prefixed spellings (preferred in new code)
    KONTEXT_JWT_SECRET_KEY = "KONTEXT_JWT_SECRET_KEY"
    KONTEXT_JWT_ISSUER = "KONTEXT_JWT_ISSUER"
    KONTEXT_JWT_AUDIENCE = "KONTEXT_JWT_AUDIENCE"


# API Configuration Environment Variables
class ApiEnvVars:
    """Environment variables for API configuration"""

    # API URLs
    API_URL = "KONTEXT_API_URL"
    INTERNAL_API_URL = "INTERNAL_KONTEXT_API_URL"
    PUBLIC_API_URL = "PUBLIC_KONTEXT_API_URL"

    # App URLs
    APP_URL = "PUBLIC_KONTEXT_APP_URL"

    # Default Values
    DEFAULT_API_URL = "http://localhost:8101"
    DEFAULT_APP_URL = "http://localhost:8002"
    # Cache Configuration
    PROJECT_CACHE_DURATION_MINUTES = "KONTEXT_PROJECT_CACHE_DURATION_MINUTES"


# Storage Environment Variables
class StorageEnvVars:
    """Environment variables for storage configuration"""

    # File Storage
    FILE_STORAGE_PATH = "FILE_STORAGE_PATH"

    # Additional local directories that file access is allowed to reach
    # (os.pathsep-separated). The managed storage path is always allowed.
    ALLOWED_PATHS = "KONTEXT_ALLOWED_PATHS"

    # Roots the kernel child process may open files in (os.pathsep-separated).
    # The stdlib-only kernel child cannot import the path policy, so the
    # supervisor computes the roots (storage + KONTEXT_ALLOWED_PATHS) and
    # passes them through the child's scrubbed environment.
    OPEN_ROOTS = "KONTEXT_OPEN_ROOTS"

    # Module whitelist/blacklist passed to the kernel child so runtime-level
    # import confinement mirrors the pre-flight policy. The stdlib-only child
    # cannot import kontext, so the supervisor computes the lists.
    WHITELISTED_MODULES = "KONTEXT_WHITELISTED_MODULES"
    BLACKLISTED_MODULES = "KONTEXT_BLACKLISTED_MODULES"


# DuckDB/Database Environment Variables
class DatabaseEnvVars:
    """Environment variables for database configuration"""

    # Extensions
    EXTENSIONS_DIR = "KONTEXT_EXTENSIONS_DIR"

    # Project Database Configuration
    PROJECT_DATABASE_URL = "PROJECT_DB_URL"
    """SQLAlchemy connection URL for the project database.
    Local mode uses SQLite (sqlite:///...); PostgreSQL is also supported, e.g.
    postgresql+psycopg://<user>:<pass>@<host>:5432/kontext_projectdb?sslmode=require
    """

    KONTEXT_PROJECT_DATABASE_URL = "KONTEXT_PROJECT_DB_URL"
    """Canonical KONTEXT_-prefixed spelling of ``PROJECT_DB_URL``."""


# Model/Agent Environment Variables
class ModelEnvVars:
    """Environment variables for model and agent configuration"""

    MODEL_PROVIDER = "MODEL_PROVIDER"

    # Provider-specific model IDs
    LM_STUDIO_MODEL = "LM_STUDIO_MODEL"
    OLLAMA_MODEL = "OLLAMA_MODEL"
    OLLAMA_CLOUD_MODEL = "OLLAMA_CLOUD_MODEL"
    OPENAI_MODEL = "OPENAI_MODEL"
    ANTHROPIC_MODEL = "ANTHROPIC_MODEL"
    OPENROUTER_MODEL = "OPENROUTER_MODEL"
    OPENAI_COMPATIBLE_MODEL = "OPENAI_COMPATIBLE_MODEL"
    DEEPSEEK_MODEL = "DEEPSEEK_MODEL"
    MISTRAL_MODEL = "MISTRAL_MODEL"
    GEMINI_MODEL = "GEMINI_MODEL"
    GOOGLE_VERTEX_MODEL = "GOOGLE_VERTEX_MODEL"
    AZURE_OPENAI_MODEL = "AZURE_OPENAI_MODEL"
    BEDROCK_MODEL = "BEDROCK_MODEL"
    BEDROCK_MODEL_ID = "BEDROCK_MODEL_ID"

    # Provider credentials/config
    LM_STUDIO_API_BASE = "LM_STUDIO_API_BASE"
    LM_STUDIO_API_KEY = "LM_STUDIO_API_KEY"
    OLLAMA_API_BASE = "OLLAMA_API_BASE"
    OLLAMA_API_KEY = "OLLAMA_API_KEY"
    OLLAMA_CLOUD_API_BASE = "OLLAMA_CLOUD_API_BASE"
    OLLAMA_CLOUD_API_KEY = "OLLAMA_CLOUD_API_KEY"
    OPENAI_API_KEY = "OPENAI_API_KEY"
    OPENAI_API_BASE = "OPENAI_API_BASE"
    ANTHROPIC_API_KEY = "ANTHROPIC_API_KEY"
    OPENROUTER_API_KEY = "OPENROUTER_API_KEY"
    OPENROUTER_API_BASE = "OPENROUTER_API_BASE"
    OPENAI_COMPATIBLE_API_KEY = "OPENAI_COMPATIBLE_API_KEY"
    OPENAI_COMPATIBLE_API_BASE = "OPENAI_COMPATIBLE_API_BASE"
    DEEPSEEK_API_KEY = "DEEPSEEK_API_KEY"
    DEEPSEEK_API_BASE = "DEEPSEEK_API_BASE"
    MISTRAL_API_KEY = "MISTRAL_API_KEY"
    MISTRAL_API_BASE = "MISTRAL_API_BASE"
    GEMINI_API_KEY = "GEMINI_API_KEY"
    GOOGLE_CLOUD_API_KEY = "GOOGLE_CLOUD_API_KEY"
    GOOGLE_CLOUD_PROJECT = "GOOGLE_CLOUD_PROJECT"
    GOOGLE_CLOUD_LOCATION = "GOOGLE_CLOUD_LOCATION"
    AZURE_OPENAI_API_KEY = "AZURE_OPENAI_API_KEY"
    AZURE_OPENAI_ENDPOINT = "AZURE_OPENAI_ENDPOINT"
    OPENAI_API_VERSION = "OPENAI_API_VERSION"
    BEDROCK_REGION = "BEDROCK_REGION"
    AWS_BEARER_TOKEN_BEDROCK = "AWS_BEARER_TOKEN_BEDROCK"

    # Agent behavior
    PROJECT_AGENT_MARKDOWN = "PROJECT_AGENT_MARKDOWN"
    PROJECT_AGENT_ADD_HISTORY = "PROJECT_AGENT_ADD_HISTORY"
    PROJECT_AGENT_NUM_HISTORY_RUNS = "PROJECT_AGENT_NUM_HISTORY_RUNS"
    PROJECT_AGENT_TELEMETRY = "PROJECT_AGENT_TELEMETRY"
    PROJECT_AGENT_TOOL_CALL_CLIENT_POLICY = "PROJECT_AGENT_TOOL_CALL_CLIENT_POLICY"
    PROJECT_AGENT_SUMMARY = "PROJECT_AGENT_SUMMARY"
    PROJECT_AGENT_DEBUG = "PROJECT_AGENT_DEBUG"
    PROJECT_AGENT_TOOL_CALL_LIMIT = "PROJECT_AGENT_TOOL_CALL_LIMIT"
    PROJECT_AGENT_REASONING_EFFORT = "PROJECT_AGENT_REASONING_EFFORT"

    # SQL
    SQL_DIALECT = "SQL_DIALECT"

    # Agent harness selection. Names the framework adapter that constructs
    # agentic systems (e.g. "agno"). Kept harness-neutral so the default can be
    # switched without editing domain code.
    AGENT_FRAMEWORK = "KONTEXT_AGENT_FRAMEWORK"

    # Comma-separated logger names owned by the active harness. These are
    # normalized onto the root JSON handler by structured logging; keeping it an
    # env var avoids hardcoding a specific framework in the common layer.
    AGENT_FRAMEWORK_LOGGERS = "KONTEXT_AGENT_FRAMEWORK_LOGGERS"


# Interactive Authentication Default Values
class InteractiveAuthDefaults:
    """Default values for interactive authentication"""

    CALLBACK_PORT = 8080
    TIMEOUT_SECONDS = 300
    AUTO_OPEN_BROWSER = True


# Job run lease Environment Variables
class JobLeaseEnvVars:
    """Environment variables for job-run claim leases and reclaim.

    A claimed run holds a lease that its worker renews while alive and
    healthy; a reaper reclaims (requeues) runs whose lease lapsed — the
    analogue of a queue visibility timeout for the DB-backed local claim.
    """

    LEASE_SECONDS = "KONTEXT_JOB_RUN_LEASE_SECONDS"
    MAX_RECLAIMS = "KONTEXT_JOB_RUN_MAX_LEASE_RECLAIMS"


# Notebook/agent Python execution Environment Variables
class PythonExecutionEnvVars:
    """Environment variables for agent-facing Python execution policy."""

    # Cap on back-to-back infrastructure failures (kernel cannot start/run)
    # before an agent-driven execution is told to stop retrying.
    MAX_CONSECUTIVE_KERNEL_FAILURES = "KONTEXT_PYTHON_MAX_CONSECUTIVE_KERNEL_FAILURES"


# All environment variables (for validation and documentation)
ALL_ENV_VARS = {
    # Authentication
    AuthEnvVars.ACCESS_TOKEN: "Access token for bearer token authentication",
    AuthEnvVars.REFRESH_TOKEN: "Refresh token for token renewal",
    AuthEnvVars.COOKIES: "Session cookies for cookie-based authentication",
    AuthEnvVars.AUTH_CALLBACK_PORT: "Port for interactive auth callback server",
    AuthEnvVars.AUTH_TIMEOUT_SECONDS: "Timeout for interactive authentication",
    AuthEnvVars.AUTH_AUTO_OPEN_BROWSER: ("Whether to auto-open browser for interactive auth"),
    # JWT Configuration
    AuthEnvVars.JWT_SECRET_KEY: "Secret key for JWT token signing and validation",
    AuthEnvVars.JWT_ISSUER: "Expected JWT issuer (default: kontext-api)",
    AuthEnvVars.JWT_AUDIENCE: "Expected JWT audience (default: kontext-platform)",
    # API Configuration
    ApiEnvVars.API_URL: "Kontext API base URL",
    ApiEnvVars.INTERNAL_API_URL: "Internal Kontext API URL (server-to-server)",
    ApiEnvVars.PUBLIC_API_URL: "Public Kontext API URL (client-facing)",
    ApiEnvVars.APP_URL: "Kontext app URL",
    # Storage
    StorageEnvVars.FILE_STORAGE_PATH: "Local file storage path",
    StorageEnvVars.ALLOWED_PATHS: (
        "Extra directories local file access may reach (os.pathsep-separated)"
    ),
    StorageEnvVars.OPEN_ROOTS: (
        "Supervisor-provided open roots for the kernel child (os.pathsep-separated)"
    ),
    StorageEnvVars.WHITELISTED_MODULES: (
        "Supervisor-provided import whitelist for the kernel child (os.pathsep-separated)"
    ),
    StorageEnvVars.BLACKLISTED_MODULES: (
        "Supervisor-provided import blacklist for the kernel child (os.pathsep-separated)"
    ),
    # Database
    DatabaseEnvVars.EXTENSIONS_DIR: "Directory path for DuckDB extensions",
    DatabaseEnvVars.PROJECT_DATABASE_URL: ("SQLAlchemy connection URL for the project database"),
    # Job run lease
    JobLeaseEnvVars.LEASE_SECONDS: ("Job-run claim lease duration in seconds (default: 300)"),
    JobLeaseEnvVars.MAX_RECLAIMS: ("Dead-letter a run after this many lease reclaims (default: 5)"),
    # Notebook/agent Python execution
    PythonExecutionEnvVars.MAX_CONSECUTIVE_KERNEL_FAILURES: (
        "Stop retrying agent Python executions after this many consecutive "
        "infrastructure failures (default: 3)"
    ),
}
