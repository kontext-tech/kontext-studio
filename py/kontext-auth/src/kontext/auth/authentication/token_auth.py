"""
Bearer token authentication with refresh capability
"""

import os

import jwt

from kontext.common.config import get_config
from kontext.common.constants import ApiEnvVars
from kontext.common.pydantic import KontextBaseModel

from .base_auth import AuthBase, AuthenticationError


class TokenAuthConfig(KontextBaseModel):
    """Configuration for token authentication"""

    access_token: str | None = None
    refresh_token: str | None = None
    api_base_url: str = ApiEnvVars.DEFAULT_API_URL
    timeout_seconds: int = 60  # Default to 1 minute

    @classmethod
    def from_tokens(
        cls,
        access_token: str,
        refresh_token: str | None = None,
        api_base_url: str | None = None,
    ) -> "TokenAuthConfig":
        """Create configuration from provided tokens"""
        if api_base_url is None:
            # Use the same logic as ApiServiceFactory for consistency
            api_base_url = os.getenv(
                ApiEnvVars.INTERNAL_API_URL,
                os.getenv(ApiEnvVars.INTERNAL_API_URL, ApiEnvVars.DEFAULT_API_URL),
            )

        return cls(
            access_token=access_token,
            refresh_token=refresh_token,
            api_base_url=api_base_url,
        )


class TokenAuth(AuthBase):
    """
    Authentication implementation for token-based authentication (access/refresh tokens)
    """

    def __init__(self, config: TokenAuthConfig):
        super().__init__()
        self.config = config
        self.refresh_token = config.refresh_token

        # If we have an access token, set it immediately as credentials
        if config.access_token:
            # We don't know the exact expiration, so assume it's valid for now
            # The refresh_if_needed method will handle refreshing when needed
            self.set_credentials(config.access_token)

    async def authenticate(self) -> bool:
        """
        Authenticate using provided access token

        Returns:
            True if authentication successful, False otherwise

        Raises:
            AuthenticationError: If no access token is available
        """
        if not self.config.access_token:
            raise AuthenticationError("No access token provided")

        self.set_credentials(self.config.access_token)
        self.logger.info("Using provided access token for authentication")

        # Validate the token by making a test API call
        try:
            self._validate_token()
            return True
        except AuthenticationError:
            # If validation fails, the token might be expired or invalid
            # We'll still return success and let the caller handle the error
            return True

    def get_user_id(self) -> str | None:
        """
        Extract user ID from the current access token

        Returns:
            User ID string if available, None otherwise
        """
        if not self.auth_credentials:
            return None

        try:
            # Decode token without verification to extract claims
            # We trust our own token here
            payload = jwt.decode(self.auth_credentials, options={"verify_signature": False})
            return payload.get("sub")
        except Exception as e:
            self.logger.warning(f"Failed to extract user ID from token: {e}")
            return None

    async def refresh_if_needed(self) -> bool:
        """
        Refresh credentials if needed and return success status

        Returns:
            True if credentials are valid/refreshed, False otherwise

        Raises:
            AuthenticationError: If refresh fails
        """
        # If we have valid credentials, we're good
        if self.auth_credentials and self.is_credentials_valid():
            return True

        # Try to refresh the token
        if self.refresh_token:
            try:
                await self._refresh_token()
                if self.auth_credentials is None:
                    raise AuthenticationError("Failed to refresh token")
                return True
            except Exception as e:
                self.logger.error(f"Failed to refresh token: {e}")
                raise AuthenticationError(f"Token refresh failed: {e}") from e

        # If no refresh token, try to use the original access token
        if self.config.access_token:
            self.set_credentials(self.config.access_token)
            return True

        raise AuthenticationError("No valid authentication credentials available")

    def _validate_token(self) -> None:
        """
        Validate the current access token locally using JwtValidator when possible.

        This function prefers distributed JWT validation (requires JWT_SECRET_KEY)
        and falls back to a minimal expiration check when a secret is not available.

        Raises:
            AuthenticationError: If token is missing or invalid/expired
        """
        if not self.auth_credentials:
            raise AuthenticationError("No access token available for validation")

        # If JWT_SECRET_KEY is configured, perform full validation
        try:
            from kontext.auth.authentication.jwt_validator import (
                JwtValidationError,
                JwtValidator,
            )

            if get_config().jwt_secret_key:
                validator = JwtValidator.from_environment()
                try:
                    validator.validate_token(self.auth_credentials)
                    self.logger.info("Access token validated successfully (local JWT validation)")
                    return
                except JwtValidationError as e:
                    self.logger.error(f"Local JWT validation failed: {e}")
                    raise AuthenticationError(f"Invalid access token: {e}") from e
            else:
                # Fallback: check expiration without signature verification
                if JwtValidator.is_token_expired(self.auth_credentials):
                    raise AuthenticationError("Access token has expired")
                self.logger.debug(
                    "Access token presence and non-expired (no signature verification)"
                )
                return
        except AuthenticationError:
            raise
        except Exception as e:
            self.logger.error(f"Error validating token: {e}")
            raise AuthenticationError(f"Token validation failed: {e}") from e

    async def _refresh_token(self) -> None:
        """
        Refresh the access token using the refresh token

        Raises:
            AuthenticationError: If refresh fails
        """
        if not self.refresh_token:
            raise AuthenticationError("No refresh token available")

        try:
            # Use AuthService for API call
            from .auth_service import AuthService

            auth_service = AuthService(self.config.api_base_url, self.config.timeout_seconds)

            response = auth_service.refresh_user_token(self.refresh_token)

            # Update tokens
            self.set_credentials(response.access_token, response.expires_in)

            # Update refresh token if provided
            if hasattr(response, "refresh_token") and response.refresh_token:
                self.refresh_token = response.refresh_token

            self.logger.info("Successfully refreshed access token")

        except Exception as e:
            self.logger.error(f"Failed to refresh token: {e}")
            raise AuthenticationError(f"Token refresh failed: {e}") from e
