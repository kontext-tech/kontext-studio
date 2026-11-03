"""SQLite runtime compatibility checks for the local server.

The local deployment uses SQLite for the project database and the agent session
stores. SQLite 3.51.0 and 3.51.1 contain a deadlock in the broken-posix-lock
detection logic (fixed in 3.51.2) that only appears with concurrent WAL access
— the normal mode of operation here, where the API process, the job worker and
agent runs open connections together.

The failure mode is a process-wide hang: the event loop blocks inside SQLite
while holding no useful work, so every request (including ``/health``) stops
responding. Reject those versions at startup instead of letting a chat session
wedge the server minutes later.
"""

from __future__ import annotations

import sqlite3

#: SQLite releases with the concurrent-WAL deadlock fixed in 3.51.2.
_UNSAFE_SQLITE_VERSIONS = frozenset({(3, 51, 0), (3, 51, 1)})


def ensure_supported_sqlite() -> None:
    """Raise when the linked SQLite has the 3.51.0/3.51.1 WAL deadlock."""
    version = tuple(sqlite3.sqlite_version_info[:3])
    if version not in _UNSAFE_SQLITE_VERSIONS:
        return

    detected = sqlite3.sqlite_version
    raise RuntimeError(
        f"SQLite {detected} has a WAL deadlock (fixed in SQLite 3.51.2) that can "
        "hang the local server. Upgrade the SQLite library used by this Python "
        "(Homebrew: `brew upgrade sqlite`; Debian/Ubuntu: upgrade `libsqlite3-0`), "
        "or use a Python build that bundles a fixed SQLite, for example "
        "`uv tool install --managed-python ...`. Reinstalling this Python package "
        "does not change the SQLite library it links against."
    )
