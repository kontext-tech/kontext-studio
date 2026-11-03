"""Shared helpers for artifact action sequencing."""

from __future__ import annotations

import time


class MonotonicActionSequencer:
    """Generate strictly increasing numeric action sequences."""

    def __init__(self, start: int | None = None) -> None:
        self._last_value = start if start is not None else int(time.time() * 1_000_000)

    def next(self) -> int:
        current_time_value = int(time.time() * 1_000_000)
        self._last_value = max(self._last_value + 1, current_time_value)
        return self._last_value
