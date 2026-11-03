"""Bootstrap and seeding for the local runtime profile."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import select

from kontext.project.local import seed_default_local_project

from .config import (
    LOCAL_DEFAULT_USER_FIRST_NAME,
    LOCAL_DEFAULT_USER_LAST_NAME,
    configure_local_runtime,
    get_local_default_user_email,
    get_local_default_user_password,
)

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from kontext.account import UserProfile


def initialize_local_mode(*, log_level: str | None = None, log_format: str | None = None) -> str:
    """Initialize the local runtime, migrations, and default data.

    Serialized across processes: the API server and the job worker both call
    this at startup against the same SQLite file, so migrations and seeding run
    under an advisory lock and the seeds are individually idempotent.
    """
    db_url = configure_local_runtime(log_level=log_level, log_format=log_format)

    import kontext.account  # noqa: F401
    from kontext.data.migrations import run_local_migrations
    from kontext.runtime.local.config import get_local_data_dir
    from kontext.runtime.model_connection_store import configure_model_resolution

    from .init_lock import local_init_lock

    configure_model_resolution()

    with local_init_lock(get_local_data_dir()):
        run_local_migrations(db_url)
        seed_default_local_admin_user()
        seed_default_local_project()
    return db_url


def complete_local_setup(
    *,
    first_name: str,
    last_name: str | None,
    email: str,
) -> UserProfile:
    """Persist an explicit local profile override for environments that need one."""
    from kontext.account import (
        UserProfile,
        is_default_local_profile,
        read_profile,
        workspace_has_user_content,
        write_profile,
    )

    existing_profile = read_profile()
    if existing_profile is not None and not is_default_local_profile(existing_profile):
        raise ValueError("Local setup is already complete.")

    # The seeded placeholder profile/project are infrastructure, not user data.
    # If real content already exists, a late setup call must not repurpose the
    # profile and silently take ownership of someone's workspace.
    if workspace_has_user_content():
        raise ValueError(
            "This local workspace already contains data, so first-time setup "
            "will not overwrite it. Reset the local database to run setup again."
        )

    profile = UserProfile(
        id=existing_profile.id if existing_profile is not None else str(uuid4()),
        first_name=first_name,
        last_name=last_name or "User",
        email=email,
        preferred_language_code="en",
    )
    if is_default_local_profile(profile):
        raise ValueError("Choose a non-default local profile to complete setup.")
    write_profile(None, profile)
    seed_default_local_project()
    return profile


def seed_default_local_admin_user() -> None:
    """Ensure local mode has a stable local admin profile for JWT bootstrap."""
    from sqlalchemy.exc import IntegrityError

    from kontext.account import _LocalProfileDB, hash_password
    from kontext.data.database import get_sync_db_session

    default_email = get_local_default_user_email()
    default_password = get_local_default_user_password()
    default_password_hash = hash_password(default_password)
    seeded_default_user = False
    repaired_legacy_users = 0

    with get_sync_db_session() as session:
        rows = session.execute(select(_LocalProfileDB)).scalars().all()
        default_user = next((row for row in rows if row.email == default_email), None)

        if default_user is None:
            default_user = _LocalProfileDB(
                id=str(uuid4()),
                first_name=LOCAL_DEFAULT_USER_FIRST_NAME,
                last_name=LOCAL_DEFAULT_USER_LAST_NAME,
                email=default_email,
                preferred_language_code="en",
                email_confirmed=True,
                password_hash=default_password_hash,
            )
            session.add(default_user)
            seeded_default_user = True
        elif not default_user.password_hash:
            default_user.password_hash = default_password_hash
            repaired_legacy_users += 1

        for row in rows:
            if not row.password_hash:
                row.password_hash = hash_password(default_password)
                repaired_legacy_users += 1

        try:
            session.commit()
        except IntegrityError:
            # Another process seeded the same unique email concurrently. The
            # init lock normally prevents this; this is a belt-and-braces guard
            # so a racing boot can never crash startup.
            session.rollback()
            logger.info(
                "Default local admin profile for %s was seeded concurrently; continuing.",
                default_email,
            )
            return

    if seeded_default_user:
        logger.warning(
            "Seeded default local admin profile for %s.",
            default_email,
        )
    elif repaired_legacy_users > 0:
        logger.warning(
            "Repaired %s legacy local user account(s) with the default local password "
            "to preserve compatibility with pre-setup databases.",
            repaired_legacy_users,
        )
