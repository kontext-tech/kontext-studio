"""
Utilities for extracting user information from JWT tokens.
"""

from kontext.auth.authentication.jwt_validator import JwtClaims
from kontext.schema import UserType, UserWithRolesModel


class JwtUserExtractor:
    """
    Utility class for extracting UserWithRolesModel from JWT claims.
    """

    @staticmethod
    def extract_user(claims: JwtClaims) -> UserWithRolesModel:
        """
        Extract a UserWithRolesModel from JwtClaims.

        Args:
            claims: The validated JWT claims.

        Returns:
            A UserWithRolesModel populated from the claims.
        """
        # Parse user_type string to UserType enum
        try:
            # Handle both string and enum if claims.user_type is already an enum
            if isinstance(claims.user_type, UserType):
                user_type_enum = claims.user_type
            else:
                user_type_enum = UserType(claims.user_type)
        except (ValueError, KeyError):
            user_type_enum = UserType.USER

        # Build a UserWithRolesModel from the token claims
        first_name = claims.display_name or "User"

        return UserWithRolesModel(
            id=claims.user_id,
            first_name=first_name,
            last_name=None,
            email=claims.email or None,
            user_type=user_type_enum,
            roles=claims.roles if claims.roles is not None else [],
            project_roles=claims.project_roles if claims.project_roles is not None else {},
            permission_claims=claims.permission_claims
            if claims.permission_claims is not None
            else [],
            is_enabled=True,
        )
