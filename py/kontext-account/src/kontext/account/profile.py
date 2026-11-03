"""
Local identity store — manages user profile, credentials and preferences
via SQLite in local mode.

Provides the local identity data used by the Kontext host contract.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field
from sqlalchemy import String, func, select
from sqlalchemy.orm import Mapped, mapped_column

from kontext.data.database import Base, get_sync_db_session


class _LocalProfileDB(Base):
    __tablename__ = "local_profile"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    first_name: Mapped[str] = mapped_column(String, nullable=False)
    last_name: Mapped[str | None] = mapped_column(String, nullable=True)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String, nullable=True)
    preferred_language_code: Mapped[str] = mapped_column(
        String, default="en", nullable=False, server_default="en"
    )
    email_confirmed: Mapped[bool] = mapped_column(default=True)


class _LocalPreferencesDB(Base):
    __tablename__ = "local_preferences"

    id: Mapped[str] = mapped_column(String, primary_key=True, default="default")
    theme: Mapped[str] = mapped_column(String, default="light")
    locale: Mapped[str] = mapped_column(String, default="en")


class _LocalPasswordResetDB(Base):
    """Ephemeral table for forgot-password reset codes."""

    __tablename__ = "local_password_resets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    email: Mapped[str] = mapped_column(String, nullable=False, index=True)
    code: Mapped[str] = mapped_column(String, nullable=False)
    expires_at: Mapped[str] = mapped_column(String, nullable=False)


class UserProfile(BaseModel):
    """Local user identity for the Kontext host contract."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    first_name: str = "Local"
    last_name: str | None = None
    email: str = "local@kontext.local"
    preferred_language_code: str = "en"

    def to_oidc_claims(self) -> dict[str, Any]:
        return {
            "sub": self.id,
            "email": self.email,
            "given_name": self.first_name,
            "family_name": self.last_name or "",
            "azp": "kontext-local",
        }


class UserPreferences(BaseModel):
    theme: str = "light"
    locale: str = "en"


_PBKDF2_ITERATIONS = 310_000
_SALT_LEN = 16
_DEFAULT_LOCAL_FIRST_NAME = "Local"
_DEFAULT_LOCAL_LAST_NAME = "Admin"
_DEFAULT_LOCAL_EMAIL = "local@kontext.local"


def _normalize_email(email: str) -> str:
    """Return a canonical representation for local-mode email lookups."""
    return email.strip().lower()


def normalize_preferred_language_code(code: str | None) -> str:
    """Collapse local profile language codes to the supported host cultures."""
    normalized = (code or "").strip().replace("_", "-").lower()
    if normalized.startswith("zh"):
        return "zh"
    if normalized.startswith("en"):
        return "en"
    return "en"


def hash_password(password: str) -> str:
    """Return a PBKDF2-HMAC-SHA256 hash of *password* as a hex string (salt:hash)."""
    salt = os.urandom(_SALT_LEN)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return salt.hex() + ":" + dk.hex()


def verify_password(password: str, stored_hash: str) -> bool:
    """Return ``True`` if *password* matches *stored_hash*."""
    try:
        salt_hex, dk_hex = stored_hash.split(":", 1)
        salt = bytes.fromhex(salt_hex)
        dk = bytes.fromhex(dk_hex)
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
        return hmac.compare_digest(candidate, dk)
    except Exception:
        return False


def load_local_profile_by_subject(sub: str) -> UserProfile | None:
    """Load a local user profile by persisted subject identifier."""
    with get_sync_db_session() as session:
        row = session.execute(
            select(_LocalProfileDB).where(_LocalProfileDB.id == sub)
        ).scalar_one_or_none()
    if not row:
        return None

    return UserProfile(
        id=row.id,
        first_name=row.first_name,
        last_name=row.last_name,
        email=row.email,
        preferred_language_code=normalize_preferred_language_code(row.preferred_language_code),
    )


def read_profile(email: str | None = None, engine: Any = None) -> UserProfile | None:
    """Return the profile matching *email*, or the first profile if email is None."""
    with get_sync_db_session() as session:
        stmt = select(_LocalProfileDB)
        if email:
            stmt = stmt.where(func.lower(_LocalProfileDB.email) == _normalize_email(email))
        else:
            stmt = stmt.limit(1)
        row = session.execute(stmt).scalar_one_or_none()
        if row is None:
            return None
        return UserProfile(
            id=row.id,
            first_name=row.first_name,
            last_name=row.last_name,
            email=row.email,
            preferred_language_code=normalize_preferred_language_code(row.preferred_language_code),
        )


def write_profile(engine: Any, profile: UserProfile, password: str | None = None) -> None:
    """Upsert profile; if *password* is provided it is hashed and stored."""
    normalized_email = _normalize_email(profile.email)
    with get_sync_db_session() as session:
        row = session.execute(
            select(_LocalProfileDB).where(func.lower(_LocalProfileDB.email) == normalized_email)
        ).scalar_one_or_none()
        if row is None:
            row = session.execute(
                select(_LocalProfileDB).where(_LocalProfileDB.id == profile.id)
            ).scalar_one_or_none()
        if row is None:
            row = _LocalProfileDB(id=profile.id)
            session.add(row)
        row.first_name = profile.first_name
        row.last_name = profile.last_name
        row.email = normalized_email
        row.preferred_language_code = normalize_preferred_language_code(
            profile.preferred_language_code
        )
        row.email_confirmed = True
        if password is not None:
            row.password_hash = hash_password(password)
        session.commit()


def is_default_local_profile(profile: UserProfile | None) -> bool:
    """Return True when *profile* still matches the seeded local placeholder."""
    if profile is None:
        return False

    default_email = os.getenv("KONTEXT_LOCAL_DEFAULT_USER_EMAIL", _DEFAULT_LOCAL_EMAIL)
    return (
        _normalize_email(profile.email) == _normalize_email(default_email)
        and profile.first_name == _DEFAULT_LOCAL_FIRST_NAME
        and (profile.last_name or "") == _DEFAULT_LOCAL_LAST_NAME
    )


def get_password_hash(email: str) -> str | None:
    """Return the stored password hash for *email*, or None."""
    with get_sync_db_session() as session:
        row = session.execute(
            select(_LocalProfileDB).where(
                func.lower(_LocalProfileDB.email) == _normalize_email(email)
            )
        ).scalar_one_or_none()
        return row.password_hash if row else None


def update_password(email: str, new_password: str) -> None:
    """Hash and persist a new password for the given email."""
    with get_sync_db_session() as session:
        row = session.execute(
            select(_LocalProfileDB).where(
                func.lower(_LocalProfileDB.email) == _normalize_email(email)
            )
        ).scalar_one_or_none()
        if row is None:
            raise ValueError(f"No local user with email {email!r}")
        row.password_hash = hash_password(new_password)
        session.commit()


def read_preferences(engine: Any = None) -> UserPreferences:
    try:
        with get_sync_db_session() as session:
            row = session.execute(
                select(_LocalPreferencesDB).where(_LocalPreferencesDB.id == "default")
            ).scalar_one_or_none()
            if row is None:
                return UserPreferences()
            return UserPreferences(theme=row.theme or "light", locale=row.locale or "en")
    except Exception:
        return UserPreferences()


def write_preferences(engine: Any, prefs: UserPreferences) -> None:
    with get_sync_db_session() as session:
        row = session.execute(
            select(_LocalPreferencesDB).where(_LocalPreferencesDB.id == "default")
        ).scalar_one_or_none()
        if row is None:
            row = _LocalPreferencesDB(id="default")
            session.add(row)
        row.theme = prefs.theme
        row.locale = prefs.locale
        session.commit()


def create_reset_code(email: str) -> str:
    """Generate, persist, and return a one-time reset code for *email*."""
    normalized_email = _normalize_email(email)
    code = secrets.token_urlsafe(32)
    expires_at = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    with get_sync_db_session() as session:
        existing = (
            session.execute(
                select(_LocalPasswordResetDB).where(
                    func.lower(_LocalPasswordResetDB.email) == normalized_email
                )
            )
            .scalars()
            .all()
        )
        for row in existing:
            session.delete(row)
        row = _LocalPasswordResetDB(
            id=str(uuid4()), email=normalized_email, code=code, expires_at=expires_at
        )
        session.add(row)
        session.commit()
    return code


def is_setup_complete(engine: Any = None) -> bool:
    """Return True once local mode should skip first-run setup.

    Setup is considered complete when the profile is no longer the seeded
    placeholder, *or* when the workspace already contains user content (a chat
    session, file, or query session). The second condition matters because the
    placeholder profile is always seeded on boot: a workspace that has been
    used must never be offered first-run setup again, which would otherwise
    repurpose the profile and take over existing data.
    """
    del engine
    profile = read_profile()
    if profile is not None and not is_default_local_profile(profile):
        return True
    return workspace_has_user_content()


def workspace_has_user_content() -> bool:
    """Return whether any non-deleted user content exists in the local DB."""
    from kontext.data.database import get_sync_db_session
    from kontext.data.models import ChatSession, ProjectFile, QuerySession

    with get_sync_db_session() as session:
        for model in (ChatSession, ProjectFile, QuerySession):
            found = session.execute(
                select(model.id).where(model.is_deleted.is_(False)).limit(1)
            ).scalar_one_or_none()
            if found is not None:
                return True
    return False


def validate_and_consume_reset_code(email: str, code: str) -> bool:
    """Return True and delete the code if valid and not expired."""
    with get_sync_db_session() as session:
        row = session.execute(
            select(_LocalPasswordResetDB).where(
                func.lower(_LocalPasswordResetDB.email) == _normalize_email(email),
                _LocalPasswordResetDB.code == code,
            )
        ).scalar_one_or_none()
        if row is None:
            return False
        try:
            expires = datetime.fromisoformat(row.expires_at)
            if datetime.now(UTC) > expires:
                return False
        except Exception:
            return False
        session.delete(row)
        session.commit()
        return True
