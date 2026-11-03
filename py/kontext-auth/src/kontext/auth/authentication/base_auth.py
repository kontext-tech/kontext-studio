"""
Authentication base classes for different authentication methods
"""

import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timedelta


class AuthBase(ABC):
    """
    Abstract base class for authentication implementations
    """

    def __init__(self):
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self.auth_credentials: str | None = None
        self.credentials_expires_at: datetime | None = None

    @abstractmethod
    async def authenticate(self) -> bool:
        """
        Perform authentication and store credentials

        Returns:
            True if authentication successful, False otherwise

        Raises:
            AuthenticationError: If authentication fails
        """
        pass

    @abstractmethod
    async def refresh_if_needed(self) -> bool:
        """
        Refresh credentials if needed

        Returns:
            True if credentials are valid/refreshed, False otherwise

        Raises:
            AuthenticationError: If refresh fails
        """
        pass

    def get_user_id(self) -> str | None:
        """
        Get the user ID associated with the current authentication

        Returns:
            User ID string if available, None otherwise
        """
        return None

    def is_credentials_valid(self) -> bool:
        """
        Check if current credentials are valid (not expired)

        This method works for time-based authentication implementations.
        Implementations that don't use time-based credentials (like some cookie auth)
        should override this method.

        Returns:
            True if credentials are valid, False otherwise
        """
        return (
            self.auth_credentials is not None
            and self.credentials_expires_at is not None
            and datetime.now(UTC) < self.credentials_expires_at
        )

    def get_credentials(self) -> str | None:
        """
        Get the current stored credentials

        Returns:
            Credentials string if available, None otherwise
        """
        return self.auth_credentials

    def set_credentials(self, credentials: str, expires_in: int | None = None) -> None:
        """
        Set credentials and optional expiration time

        Args:
            credentials: The credentials (token, cookie string, etc.)
            expires_in: Credential lifetime in seconds (optional)
        """
        self.auth_credentials = credentials
        if expires_in is not None:
            # Set expiration with 60 second buffer
            self.credentials_expires_at = datetime.now(UTC) + timedelta(seconds=expires_in - 60)
        else:
            self.credentials_expires_at = None


class AuthenticationError(Exception):
    """Exception raised when authentication fails"""

    pass
