"""
JWT token validation and claims extraction.

This module provides distributed JWT validation without requiring API calls
to the .NET backend. It uses PyJWT to decode and validate JWT tokens using
the shared secret key.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import jwt
from jwt.exceptions import (
    DecodeError,
    ExpiredSignatureError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
)

from kontext.auth.constants import JwtConstants
from kontext.common.utils.datetime_utils import utc_now

logger = logging.getLogger(__name__)


@dataclass
class JwtClaims:
    """Extracted claims from a validated JWT token."""

    user_id: str
    email: str
    display_name: str
    user_type: str
    jti: str
    roles: list[str]
    project_roles: dict[str, list[str]]  # {project_id: [role_types]}
    permission_claims: list[str]  # Permission claims like "projects.read", "queries.execute"
    expires_at: datetime
    issued_at: datetime


class JwtValidationError(Exception):
    """Raised when JWT validation fails."""

    pass


class JwtValidator:
    """
    Validates JWT tokens and extracts claims without calling the API.

    This allows the Python services to validate authentication independently,
    improving performance and reducing coupling to the .NET API.
    """

    def __init__(
        self,
        secret_key: str,
        issuer: str = "kontext-api",
        audience: str = "kontext-platform",
        verify_exp: bool = True,
    ):
        """
        Initialize the JWT validator.

        Args:
            secret_key: The JWT signing secret key (must match .NET configuration)
            issuer: Expected token issuer (default: "kontext-api")
            audience: Expected token audience (default: "kontext-platform")
            verify_exp: Whether to verify token expiration (default: True)
        """
        if not secret_key:
            raise ValueError("JWT secret key is required")

        if len(secret_key) < 32:
            raise ValueError("JWT secret key must be at least 32 characters")

        self.secret_key = secret_key
        self.issuer = issuer
        self.audience = audience
        self.verify_exp = verify_exp
        self.algorithms = ["HS256"]

    @classmethod
    def from_environment(cls) -> "JwtValidator":
        """
        Create a JWT validator from settings.

        Reads the JWT secret/issuer/audience through the settings singleton
        (``KONTEXT_JWT_*`` canonical names, with the legacy ``JWT_*`` names
        accepted).

        Returns:
            JwtValidator instance configured from settings

        Raises:
            ValueError: If JWT_SECRET_KEY is not set
        """
        from kontext.common.config import get_config

        config = get_config()
        secret_key = config.jwt_secret_key
        if not secret_key:
            raise ValueError("JWT_SECRET_KEY environment variable is required for JWT validation")

        # Allow customization of issuer/audience via settings (with defaults)
        # Defaults match the .NET backend configuration
        return cls(
            secret_key=secret_key,
            issuer=config.jwt_issuer,
            audience=config.jwt_audience,
        )

    def validate_token(self, token: str) -> JwtClaims:
        """
        Validate a JWT token and extract claims.

        Args:
            token: The JWT token string (without "Bearer " prefix)

        Returns:
            JwtClaims object with extracted user information

        Raises:
            JwtValidationError: If token is invalid, expired, or malformed
        """
        if not token:
            raise JwtValidationError("Token is empty")

        try:
            # Decode and validate the JWT token
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=self.algorithms,
                issuer=self.issuer,
                audience=self.audience,
                options={"verify_exp": self.verify_exp},
            )

            logger.info(f"Successfully validated JWT for user {payload.get('sub')}")
            return self._extract_claims_from_payload(payload)

        except ExpiredSignatureError as e:
            logger.warning("JWT token expired")
            raise JwtValidationError("Token has expired") from e
        except InvalidSignatureError as e:
            logger.warning("JWT token has invalid signature")
            raise JwtValidationError("Invalid token signature") from e
        except InvalidIssuerError as e:
            logger.warning(f"JWT token has invalid issuer (expected: {self.issuer})")
            raise JwtValidationError("Invalid token issuer") from e
        except InvalidAudienceError as e:
            logger.warning(f"JWT token has invalid audience (expected: {self.audience})")
            raise JwtValidationError("Invalid token audience") from e
        except DecodeError as e:
            logger.warning("JWT token decode failed")
            raise JwtValidationError("Malformed token") from e
        except Exception as e:
            logger.error(f"Unexpected error validating JWT: {e}", exc_info=True)
            raise JwtValidationError(f"Token validation failed: {e}") from e

    @staticmethod
    def _extract_claims_from_payload(payload: dict) -> JwtClaims:
        """Extract JwtClaims from a decoded payload dictionary."""
        ver = payload.get(JwtConstants.VERSION_CLAIM_TYPE)
        if ver != JwtConstants.CURRENT_VERSION and ver != str(JwtConstants.CURRENT_VERSION):
            raise JwtValidationError("Unsupported token version")

        user_id = payload.get("sub")
        if not user_id:
            raise JwtValidationError("Token missing 'sub' (user ID) claim")

        email = payload.get("email", "")
        display_name = payload.get("name", "")
        user_type = payload.get("user_type", "User")
        jti = payload.get("jti", "")

        # Extract role claims
        all_roles = []
        for key, value in payload.items():
            if key.endswith("/role"):
                if isinstance(value, list):
                    all_roles.extend(value)
                else:
                    all_roles.append(value)

        roles = []
        project_roles: dict[str, list[str]] = {}

        for role in all_roles:
            if not isinstance(role, str):
                continue

            role = role.strip()

            if ":" in role and role.lower().startswith("project."):
                try:
                    role_type, project_id = role.split(":", 1)
                    role_type_normalized = (
                        (role_type.split(".", 1)[1] if "." in role_type else role_type)
                        .strip()
                        .lower()
                    )

                    project_id = project_id.strip()
                    try:
                        project_id_normalized = str(UUID(project_id)).lower()
                    except Exception:
                        project_id_normalized = project_id.lower()

                    if project_id_normalized not in project_roles:
                        project_roles[project_id_normalized] = []
                    if role_type_normalized not in project_roles[project_id_normalized]:
                        project_roles[project_id_normalized].append(role_type_normalized)
                except ValueError:
                    roles.append(role)
            else:
                roles.append(role)

        permission_claims: list[str] = []
        permission_value = payload.get("permission")
        if permission_value:
            if isinstance(permission_value, list):
                permission_claims.extend(permission_value)
            else:
                permission_claims.append(permission_value)

        exp = payload.get("exp")
        iat = payload.get("iat")

        expires_at = (
            datetime.fromtimestamp(exp, tz=UTC) if exp else datetime.max.replace(tzinfo=UTC)
        )
        issued_at = datetime.fromtimestamp(iat, tz=UTC) if iat else datetime.min.replace(tzinfo=UTC)

        return JwtClaims(
            user_id=user_id,
            email=email,
            display_name=display_name,
            user_type=user_type,
            jti=jti,
            roles=roles,
            project_roles=project_roles,
            permission_claims=permission_claims,
            expires_at=expires_at,
            issued_at=issued_at,
        )

    @staticmethod
    def is_token_expired(token: str) -> bool:
        """
        Check if a token is expired without full validation.

        Args:
            token: The JWT token string

        Returns:
            True if token is expired, False otherwise
        """
        try:
            # Decode without verification to check expiration
            payload = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
            exp = payload.get("exp")
            if not exp:
                return False

            expires_at = datetime.fromtimestamp(exp, tz=UTC)
            return utc_now() >= expires_at

        except Exception as e:
            logger.warning(f"Error checking token expiration: {e}")
            return True  # Assume expired on error
