"""
Unit tests for JWT token validation and claims extraction.

Tests cover:
- Token validation with correct credentials
- Token validation failures (expired, invalid signature, wrong issuer/audience)
- Claims extraction (user info, roles, project roles)
- Environment-based configuration
- Edge cases and error handling
"""

import os
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt
import pytest

from kontext.auth import JwtConstants, SystemRoles
from kontext.auth.authentication.jwt_validator import (
    JwtClaims,
    JwtValidationError,
    JwtValidator,
)
from kontext.common.utils.datetime_utils import utc_now


class TestJwtValidator:
    """Test suite for JwtValidator class."""

    @pytest.fixture
    def secret_key(self):
        """Valid secret key for testing (32+ characters)."""
        return "test-secret-key-with-sufficient-length-for-hs256"

    @pytest.fixture
    def validator(self, secret_key):
        """Create a validator instance for testing."""
        return JwtValidator(
            secret_key=secret_key, issuer="kontext-api", audience="kontext-platform"
        )

    @pytest.fixture
    def valid_payload(self):
        """Create a valid JWT payload."""
        return {
            JwtConstants.VERSION_CLAIM_TYPE: JwtConstants.CURRENT_VERSION,
            "sub": "123e4567-e89b-12d3-a456-426614174000",
            "email": "test@example.com",
            "name": "Test User",
            "user_type": "User",
            "jti": "jwt-id-123",
            "http://schemas.microsoft.com/ws/2008/06/identity/claims/role": [
                "User",
                SystemRoles.ADMINISTRATOR,
                "Project.Admin:project-123",
                "Project.Editor:project-456",
                "Project.Reader:project-123",
            ],
            "exp": int((utc_now() + timedelta(hours=1)).timestamp()),
            "iat": int(utc_now().timestamp()),
            "iss": "kontext-api",
            "aud": "kontext-platform",
        }

    def create_token(self, payload, secret_key):
        """Helper to create a JWT token."""
        return jwt.encode(payload, secret_key, algorithm="HS256")

    def create_token_v2(self, payload, secret_key):
        """Helper to create a version-2 JWT token."""
        payload_v2 = dict(payload)
        payload_v2.setdefault(JwtConstants.VERSION_CLAIM_TYPE, JwtConstants.CURRENT_VERSION)
        return self.create_token(payload_v2, secret_key)

    def test_init_with_valid_secret_key(self, secret_key):
        """Test validator initialization with valid secret key."""
        validator = JwtValidator(secret_key=secret_key)
        assert validator.secret_key == secret_key
        assert validator.issuer == "kontext-api"
        assert validator.audience == "kontext-platform"
        assert validator.verify_exp is True
        assert validator.algorithms == ["HS256"]

    def test_init_with_custom_issuer_audience(self, secret_key):
        """Test validator initialization with custom issuer and audience."""
        validator = JwtValidator(
            secret_key=secret_key,
            issuer="custom-issuer",
            audience="custom-audience",
            verify_exp=False,
        )
        assert validator.issuer == "custom-issuer"
        assert validator.audience == "custom-audience"
        assert validator.verify_exp is False

    def test_init_with_empty_secret_key(self):
        """Test validator initialization fails with empty secret key."""
        with pytest.raises(ValueError, match="JWT secret key is required"):
            JwtValidator(secret_key="")

    def test_init_with_short_secret_key(self):
        """Test validator initialization fails with short secret key."""
        with pytest.raises(ValueError, match="at least 32 characters"):
            JwtValidator(secret_key="short-key")

    def test_from_environment_success(self):
        """Test creating validator from environment variables."""
        with patch.dict(
            os.environ,
            {
                "JWT_SECRET_KEY": "test-secret-key-with-sufficient-length-for-hs256",
                "JWT_ISSUER": "test-issuer",
                "JWT_AUDIENCE": "test-audience",
            },
        ):
            validator = JwtValidator.from_environment()
            assert validator.issuer == "test-issuer"
            assert validator.audience == "test-audience"

    def test_from_environment_default_values(self):
        """Test default issuer and audience when not specified."""
        with patch.dict(
            os.environ,
            {
                "JWT_SECRET_KEY": "test-secret-key-with-sufficient-length-for-hs256",
            },
        ):
            validator = JwtValidator.from_environment()
            assert validator.issuer == "kontext-api"
            assert validator.audience == "kontext-platform"

    def test_from_environment_missing_secret_key(self):
        """Test from_environment fails without JWT_SECRET_KEY."""
        with (
            patch.dict(os.environ, {}, clear=True),
            pytest.raises(ValueError, match="JWT_SECRET_KEY environment variable is required"),
        ):
            JwtValidator.from_environment()

    def test_validate_token_success(self, validator, valid_payload, secret_key):
        """Test successful token validation with all claims."""
        token = self.create_token_v2(valid_payload, secret_key)
        claims = validator.validate_token(token)

        assert isinstance(claims, JwtClaims)
        assert claims.user_id == "123e4567-e89b-12d3-a456-426614174000"
        assert claims.email == "test@example.com"
        assert claims.display_name == "Test User"
        assert claims.user_type == "User"
        assert claims.jti == "jwt-id-123"

    def test_validate_token_extracts_system_roles(self, validator, valid_payload, secret_key):
        """Test token validation extracts system roles correctly."""
        token = self.create_token_v2(valid_payload, secret_key)
        claims = validator.validate_token(token)

        assert "User" in claims.roles
        assert SystemRoles.ADMINISTRATOR in claims.roles
        # Project roles should NOT be in system roles
        assert not any(role.startswith("Project.") for role in claims.roles)

    def test_validate_token_extracts_project_roles(self, validator, valid_payload, secret_key):
        """Test token validation extracts and parses project roles correctly."""
        token = self.create_token_v2(valid_payload, secret_key)
        claims = validator.validate_token(token)

        assert "project-123" in claims.project_roles
        assert "admin" in claims.project_roles["project-123"]
        assert "reader" in claims.project_roles["project-123"]

        assert "project-456" in claims.project_roles
        assert "editor" in claims.project_roles["project-456"]

    def test_validate_token_with_single_role(self, validator, secret_key):
        """Test token validation when role claim is a single string (not list)."""
        payload = {
            JwtConstants.VERSION_CLAIM_TYPE: JwtConstants.CURRENT_VERSION,
            "sub": "user-123",
            "email": "test@example.com",
            "name": "Test",
            "user_type": "User",
            "jti": "jti-123",
            "http://schemas.microsoft.com/ws/2008/06/identity/claims/role": "User",
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.now(UTC).timestamp()),
            "iss": "kontext-api",
            "aud": "kontext-platform",
        }
        token = self.create_token_v2(payload, secret_key)
        claims = validator.validate_token(token)

        assert claims.roles == ["User"]

    def test_validate_token_normalizes_project_role_types(self, validator, secret_key):
        """Test project role types are normalized to lowercase."""
        payload = {
            JwtConstants.VERSION_CLAIM_TYPE: JwtConstants.CURRENT_VERSION,
            "sub": "user-123",
            "email": "test@example.com",
            "name": "Test",
            "user_type": "User",
            "jti": "jti-123",
            "http://schemas.microsoft.com/ws/2008/06/identity/claims/role": [
                "Project.Admin:proj-1",
                "Project.Owner:proj-2",
                "Project.Contributor:proj-1",
            ],
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.now(UTC).timestamp()),
            "iss": "kontext-api",
            "aud": "kontext-platform",
        }
        token = self.create_token_v2(payload, secret_key)
        claims = validator.validate_token(token)

        assert claims.project_roles["proj-1"] == ["admin", "contributor"]
        assert claims.project_roles["proj-2"] == ["owner"]

    def test_validate_token_extracts_permission_claims(self, validator, secret_key):
        """Test permission claims are extracted from JWT token."""
        payload = {
            JwtConstants.VERSION_CLAIM_TYPE: JwtConstants.CURRENT_VERSION,
            "sub": "user-123",
            "email": "test@example.com",
            "name": "Test",
            "user_type": "ServiceAccount",
            "jti": "jti-123",
            "permission": [
                "projects.read",
                "queries.execute",
                "chats.create",
            ],
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.now(UTC).timestamp()),
            "iss": "kontext-api",
            "aud": "kontext-platform",
        }
        token = self.create_token_v2(payload, secret_key)
        claims = validator.validate_token(token)

        assert claims.permission_claims == [
            "projects.read",
            "queries.execute",
            "chats.create",
        ]
        assert claims.user_type == "ServiceAccount"

    def test_validate_token_extracts_single_permission_claim(self, validator, secret_key):
        """Test single permission claim is extracted correctly."""
        payload = {
            JwtConstants.VERSION_CLAIM_TYPE: JwtConstants.CURRENT_VERSION,
            "sub": "user-123",
            "email": "test@example.com",
            "name": "Test",
            "user_type": "User",
            "jti": "jti-123",
            "permission": "projects.read",
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.now(UTC).timestamp()),
            "iss": "kontext-api",
            "aud": "kontext-platform",
        }
        token = self.create_token_v2(payload, secret_key)
        claims = validator.validate_token(token)

        assert claims.permission_claims == ["projects.read"]

    def test_validate_token_empty_permission_claims(self, validator, secret_key):
        """Test empty permission claims when none in token."""
        payload = {
            JwtConstants.VERSION_CLAIM_TYPE: JwtConstants.CURRENT_VERSION,
            "sub": "user-123",
            "email": "test@example.com",
            "name": "Test",
            "user_type": "User",
            "jti": "jti-123",
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.now(UTC).timestamp()),
            "iss": "kontext-api",
            "aud": "kontext-platform",
        }
        token = self.create_token_v2(payload, secret_key)
        claims = validator.validate_token(token)

        assert claims.permission_claims == []

    def test_validate_token_empty_token(self, validator):
        """Test validation fails with empty token."""
        with pytest.raises(JwtValidationError, match="Token is empty"):
            validator.validate_token("")

    def test_validate_token_expired(self, validator, secret_key):
        """Test validation fails with expired token."""
        payload = {
            JwtConstants.VERSION_CLAIM_TYPE: JwtConstants.CURRENT_VERSION,
            "sub": "user-123",
            "email": "test@example.com",
            "name": "Test",
            "user_type": "User",
            "jti": "jti-123",
            "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
            "iat": int(datetime.now(UTC).timestamp()),
            "iss": "kontext-api",
            "aud": "kontext-platform",
        }
        token = self.create_token_v2(payload, secret_key)

        with pytest.raises(JwtValidationError, match="Token has expired"):
            validator.validate_token(token)

    def test_validate_token_invalid_signature(self, validator, valid_payload):
        """Test validation fails with invalid signature."""
        # Create token with different secret key
        wrong_secret = "wrong-secret-key-that-is-long-enough-for-hs256"
        token = self.create_token_v2(valid_payload, wrong_secret)

        with pytest.raises(JwtValidationError, match="Invalid token signature"):
            validator.validate_token(token)

    def test_validate_token_invalid_issuer(self, secret_key, valid_payload):
        """Test validation fails with wrong issuer."""
        validator = JwtValidator(
            secret_key=secret_key, issuer="expected-issuer", audience="kontext-platform"
        )
        token = self.create_token_v2(valid_payload, secret_key)

        with pytest.raises(JwtValidationError, match="Invalid token issuer"):
            validator.validate_token(token)

    def test_validate_token_invalid_audience(self, secret_key, valid_payload):
        """Test validation fails with wrong audience."""
        validator = JwtValidator(
            secret_key=secret_key, issuer="kontext-api", audience="expected-audience"
        )
        token = self.create_token_v2(valid_payload, secret_key)

        with pytest.raises(JwtValidationError, match="Invalid token audience"):
            validator.validate_token(token)

    def test_validate_token_malformed(self, validator):
        """Test validation fails with malformed token."""
        with pytest.raises(JwtValidationError, match="Malformed token"):
            validator.validate_token("not.a.valid.jwt.token")

    def test_validate_token_missing_sub_claim(self, validator, secret_key):
        """Test validation fails when sub (user ID) claim is missing."""
        payload = {
            JwtConstants.VERSION_CLAIM_TYPE: JwtConstants.CURRENT_VERSION,
            "email": "test@example.com",
            "name": "Test",
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            "iss": "kontext-api",
            "aud": "kontext-platform",
        }
        token = self.create_token_v2(payload, secret_key)

        with pytest.raises(JwtValidationError, match="missing 'sub'"):
            validator.validate_token(token)

    def test_validate_token_with_defaults_for_optional_claims(self, validator, secret_key):
        """Test validation succeeds with minimal required claims."""
        payload = {
            JwtConstants.VERSION_CLAIM_TYPE: JwtConstants.CURRENT_VERSION,
            "sub": "user-123",
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            "iss": "kontext-api",
            "aud": "kontext-platform",
        }
        token = self.create_token_v2(payload, secret_key)
        claims = validator.validate_token(token)

        assert claims.user_id == "user-123"
        assert claims.email == ""
        assert claims.display_name == ""
        assert claims.user_type == "User"
        assert claims.jti == ""
        assert claims.roles == []
        assert claims.project_roles == {}

    def test_validate_token_extracts_timestamps(self, validator, valid_payload, secret_key):
        """Test validation extracts expiration and issued timestamps."""
        token = self.create_token_v2(valid_payload, secret_key)
        claims = validator.validate_token(token)

        assert isinstance(claims.expires_at, datetime)
        assert isinstance(claims.issued_at, datetime)
        assert claims.expires_at > claims.issued_at
        assert claims.expires_at.tzinfo == UTC
        assert claims.issued_at.tzinfo == UTC

    def test_validate_token_handles_malformed_project_role(self, validator, secret_key):
        """Test validation handles project roles without colon separator."""
        payload = {
            JwtConstants.VERSION_CLAIM_TYPE: JwtConstants.CURRENT_VERSION,
            "sub": "user-123",
            "email": "test@example.com",
            "name": "Test",
            "user_type": "User",
            "jti": "jti-123",
            "http://schemas.microsoft.com/ws/2008/06/identity/claims/role": [
                "User",
                "Project.AdminWithoutProjectId",  # Malformed - no colon
            ],
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.now(UTC).timestamp()),
            "iss": "kontext-api",
            "aud": "kontext-platform",
        }
        token = self.create_token_v2(payload, secret_key)
        claims = validator.validate_token(token)

        # Malformed project role should be treated as system role
        assert "User" in claims.roles
        assert "Project.AdminWithoutProjectId" in claims.roles
        assert claims.project_roles == {}

    def test_validate_token_deduplicates_project_roles(self, validator, secret_key):
        """Test validation deduplicates project roles for same project."""
        payload = {
            JwtConstants.VERSION_CLAIM_TYPE: JwtConstants.CURRENT_VERSION,
            "sub": "user-123",
            "email": "test@example.com",
            "name": "Test",
            "user_type": "User",
            "jti": "jti-123",
            "http://schemas.microsoft.com/ws/2008/06/identity/claims/role": [
                "Project.Admin:proj-1",
                "Project.Admin:proj-1",  # Duplicate
                "Project.Editor:proj-1",
            ],
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.now(UTC).timestamp()),
            "iss": "kontext-api",
            "aud": "kontext-platform",
        }
        token = self.create_token_v2(payload, secret_key)
        claims = validator.validate_token(token)

        # Should only have admin once
        assert claims.project_roles["proj-1"].count("admin") == 1
        assert "editor" in claims.project_roles["proj-1"]

    def test_is_token_expired_with_expired_token(self, validator, secret_key):
        """Test is_token_expired returns True for expired token."""
        payload = {
            JwtConstants.VERSION_CLAIM_TYPE: JwtConstants.CURRENT_VERSION,
            "sub": "user-123",
            "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
            "iss": "kontext-api",
            "aud": "kontext-platform",
        }
        token = self.create_token_v2(payload, secret_key)

        assert validator.is_token_expired(token) is True

    def test_is_token_expired_with_valid_token(self, validator, secret_key):
        """Test is_token_expired returns False for valid token."""
        payload = {
            JwtConstants.VERSION_CLAIM_TYPE: JwtConstants.CURRENT_VERSION,
            "sub": "user-123",
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            "iss": "kontext-api",
            "aud": "kontext-platform",
        }
        token = self.create_token_v2(payload, secret_key)

        assert validator.is_token_expired(token) is False

    def test_is_token_expired_without_exp_claim(self, validator, secret_key):
        """Test is_token_expired returns False when exp claim is missing."""
        payload = {
            JwtConstants.VERSION_CLAIM_TYPE: JwtConstants.CURRENT_VERSION,
            "sub": "user-123",
            "iss": "kontext-api",
            "aud": "kontext-platform",
        }
        token = self.create_token_v2(payload, secret_key)

        assert validator.is_token_expired(token) is False

    def test_is_token_expired_with_malformed_token(self, validator):
        """Test is_token_expired returns True for malformed token."""
        assert validator.is_token_expired("malformed.token") is True

    def test_validate_token_with_multiple_role_claim_keys(self, validator, secret_key):
        """Test validation extracts roles from claim key ending with /role."""
        payload = {
            JwtConstants.VERSION_CLAIM_TYPE: JwtConstants.CURRENT_VERSION,
            "sub": "user-123",
            "email": "test@example.com",
            "name": "Test",
            "user_type": "User",
            "jti": "jti-123",
            "http://schemas.microsoft.com/ws/2008/06/identity/claims/role": [
                "User",
                SystemRoles.ADMINISTRATOR,
            ],
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            "iat": int(datetime.now(UTC).timestamp()),
            "iss": "kontext-api",
            "aud": "kontext-platform",
        }
        token = self.create_token_v2(payload, secret_key)
        claims = validator.validate_token(token)

        assert "User" in claims.roles
        assert SystemRoles.ADMINISTRATOR in claims.roles

    def test_validate_token_skip_expiration_check(self, secret_key):
        """Test validation can skip expiration check when verify_exp=False."""
        validator = JwtValidator(
            secret_key=secret_key,
            issuer="kontext-api",
            audience="kontext-platform",
            verify_exp=False,
        )

        payload = {
            JwtConstants.VERSION_CLAIM_TYPE: JwtConstants.CURRENT_VERSION,
            "sub": "user-123",
            "email": "test@example.com",
            "name": "Test",
            "user_type": "User",
            "jti": "jti-123",
            "exp": int((datetime.now(UTC) - timedelta(hours=1)).timestamp()),
            "iat": int(datetime.now(UTC).timestamp()),
            "iss": "kontext-api",
            "aud": "kontext-platform",
        }
        token = self.create_token_v2(payload, secret_key)

        # Should succeed even though token is expired
        claims = validator.validate_token(token)
        assert claims.user_id == "user-123"

    def test_validate_token_missing_jwt_ver_claim(self, validator, secret_key):
        """Test validation fails when jwt_ver claim is missing."""
        payload = {
            "sub": "user-123",
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            "iss": "kontext-api",
            "aud": "kontext-platform",
        }
        token = self.create_token(payload, secret_key)

        with pytest.raises(JwtValidationError, match="Unsupported token version"):
            validator.validate_token(token)

    def test_validate_token_unsupported_jwt_ver_claim(self, validator, secret_key):
        """Test validation fails when jwt_ver claim has an unsupported value."""
        payload = {
            JwtConstants.VERSION_CLAIM_TYPE: 1,
            "sub": "user-123",
            "exp": int((datetime.now(UTC) + timedelta(hours=1)).timestamp()),
            "iss": "kontext-api",
            "aud": "kontext-platform",
        }
        token = self.create_token(payload, secret_key)

        with pytest.raises(JwtValidationError, match="Unsupported token version"):
            validator.validate_token(token)

    def test_jwt_claims_dataclass_structure(self):
        """Test JwtClaims dataclass has correct structure."""
        claims = JwtClaims(
            user_id="test-id",
            email="test@example.com",
            display_name="Test User",
            user_type="User",
            jti="jti-123",
            roles=["User", "Admin"],
            project_roles={"proj-1": ["admin"]},
            permission_claims=["projects.read", "queries.execute"],
            expires_at=datetime.now(UTC),
            issued_at=datetime.now(UTC),
        )

        assert claims.user_id == "test-id"
        assert claims.email == "test@example.com"
        assert claims.display_name == "Test User"
        assert claims.user_type == "User"
        assert claims.jti == "jti-123"
        assert claims.roles == ["User", "Admin"]
        assert claims.project_roles == {"proj-1": ["admin"]}
        assert claims.permission_claims == ["projects.read", "queries.execute"]
        assert isinstance(claims.expires_at, datetime)
        assert isinstance(claims.issued_at, datetime)
