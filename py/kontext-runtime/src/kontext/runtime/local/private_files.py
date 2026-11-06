"""Owner-only file helpers for local secrets."""

from __future__ import annotations

import contextlib
import os
from pathlib import Path


def read_private_file(path: Path) -> str | None:
    """Return the stripped contents, repairing the file mode, or None."""
    try:
        value = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    if not value:
        return None
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)
    return value


def write_private_file(path: Path, content: str, *, exclusive: bool = False) -> bool:
    """Write *content* at mode 0600; return False when *exclusive* loses a race."""
    flags = os.O_WRONLY | os.O_CREAT | (os.O_EXCL if exclusive else os.O_TRUNC)
    try:
        descriptor = os.open(path, flags, 0o600)
    except FileExistsError:
        return False
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())
    with contextlib.suppress(OSError):
        os.chmod(path, 0o600)
    return True
