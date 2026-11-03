"""
Environment and service utilities for Kontext.
"""

import os


def is_local_dev_environment(environment: str | None = None) -> bool:
    """Return True when running in a local/development environment.

    This is intentionally simple and shared across Python services.

    Args:
        environment: Optional explicit environment name override.
            If omitted, reads from the `ENVIRONMENT` environment variable.

    Returns:
        True for local/dev-style environments, False otherwise.
    """

    env = (environment or os.getenv("ENVIRONMENT") or "production").lower()
    return env in ("development", "dev", "local")
