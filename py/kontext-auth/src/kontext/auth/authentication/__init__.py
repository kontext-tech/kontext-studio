"""
Authentication module for Kontext Auth

This module provides comprehensive authentication support including:
- Token authentication (Bearer tokens with refresh)
- Interactive authentication (Browser-based for local development)
- JWT validation (Distributed token validation without API calls)

The AuthManager remains the main entry point for package consumers.
"""

# Enhanced authentication system (recommended)
from .auth_manager import (
    AuthManager,
    create_interactive_auth_manager,
    create_token_auth_manager,
)

# Services
from .auth_service import AuthService
from .base_auth import AuthBase, AuthenticationError
from .interactive_auth import InteractiveAuth, InteractiveAuthConfig

# JWT validation (distributed authentication)
from .jwt_validator import JwtClaims, JwtValidationError, JwtValidator
from .token_auth import TokenAuth, TokenAuthConfig

__all__ = [
    "AuthBase",
    # Enhanced authentication
    "AuthManager",
    # Services
    "AuthService",
    "AuthenticationError",
    "InteractiveAuth",
    "InteractiveAuthConfig",
    "JwtClaims",
    "JwtValidationError",
    # JWT validation
    "JwtValidator",
    # Configurations
    "TokenAuth",
    "TokenAuthConfig",
    "create_interactive_auth_manager",
    # Convenience factory functions
    "create_token_auth_manager",
]
