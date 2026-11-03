"""Authentication Manager with simplified naming."""

import logging
import os
from collections.abc import Mapping

from kontext.common.constants import ApiEnvVars, AuthEnvVars

from .base_auth import AuthBase, AuthenticationError
from .interactive_auth import InteractiveAuth, InteractiveAuthConfig
from .token_auth import TokenAuth, TokenAuthConfig

logger = logging.getLogger(__name__)


class AuthManager:
    """
    Main authentication manager that coordinates different auth implementations
    """

    def __init__(self, auth: AuthBase):
        """
        Initialize with a specific auth implementation

        Args:
            auth: The auth implementation to use
        """
        self.auth = auth

    @staticmethod
    def _get_api_url() -> str:
        """
        Get the API URL from environment variables with fallback hierarchy

        Returns:
            API URL string
        """
        return os.getenv(
            ApiEnvVars.INTERNAL_API_URL,
            os.getenv(ApiEnvVars.PUBLIC_API_URL, ApiEnvVars.DEFAULT_API_URL),
        )

    @classmethod
    def from_environment(cls) -> "AuthManager":
        """
        Create AuthManager by detecting authentication method from environment variables.

        Uses a bearer access token from the environment when present. Local-first
        deployments mint their own tokens and do not use a hosted service account.

        Returns:
            AuthManager configured with the appropriate auth implementation
        """
        access_token = os.getenv(AuthEnvVars.ACCESS_TOKEN)
        refresh_token = os.getenv(AuthEnvVars.REFRESH_TOKEN)

        if access_token:
            logger.info(f"Detected bearer token in {AuthEnvVars.ACCESS_TOKEN}")
            config = TokenAuthConfig.from_tokens(
                access_token=access_token,
                refresh_token=refresh_token,
                api_base_url=cls._get_api_url(),
            )
            return cls(TokenAuth(config))

        raise AuthenticationError(
            f"No authentication configured. Set {AuthEnvVars.ACCESS_TOKEN} or use "
            "one of the interactive/token AuthManager factories."
        )

    @classmethod
    def from_headers(cls, headers: Mapping[str, str]) -> "AuthManager":
        """
        Create AuthManager from HTTP headers.

        Supports Bearer token authentication.

        Args:
            headers: Request headers containing authentication information

        Returns:
            AuthManager configured with appropriate auth implementation

        Raises:
            AuthenticationError: If authentication is missing or invalid
        """
        # Check for Bearer token authentication (case-insensitive header lookup)
        auth_header = None
        for header_name, header_value in headers.items():
            if header_name.lower() == "authorization":
                auth_header = header_value
                break

        if auth_header and auth_header.startswith("Bearer "):
            access_token = auth_header[7:]  # Remove "Bearer " prefix
            if not access_token:
                raise AuthenticationError("Bearer token is empty")

            # Create token auth with proper API URL
            api_url = cls._get_api_url()
            config = TokenAuthConfig.from_tokens(access_token, api_base_url=api_url)
            auth = TokenAuth(config)
            return cls(auth)

        # No authentication found
        raise AuthenticationError(
            "Authentication required. Provide Bearer token in Authorization header"
        )

    def get_user_id(self) -> str | None:
        """
        Get the user ID associated with the current authentication

        Returns:
            User ID string if available, None otherwise
        """
        return self.auth.get_user_id()

    async def authenticate(self) -> bool:
        """
        Perform authentication if needed

        Returns:
            True if authentication successful, False otherwise

        Raises:
            AuthenticationError: If authentication fails
        """
        return await self.auth.authenticate()

    async def refresh_if_needed(self) -> bool:
        """
        Refresh authentication if needed

        Returns:
            True if credentials are valid/refreshed, False otherwise

        Raises:
            AuthenticationError: If refresh fails
        """
        return await self.auth.refresh_if_needed()


# Convenience factory methods for specific auth types
def create_token_auth_manager(config: TokenAuthConfig) -> AuthManager:
    """Create AuthManager with token authentication"""
    auth = TokenAuth(config)
    return AuthManager(auth)


def create_interactive_auth_manager(config: InteractiveAuthConfig) -> AuthManager:
    """Create AuthManager with interactive authentication"""
    auth = InteractiveAuth(config)
    return AuthManager(auth)
