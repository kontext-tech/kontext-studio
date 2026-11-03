"""Helpers for draining async client finalizers before loop shutdown."""

from __future__ import annotations

import asyncio
import gc


async def drain_async_finalizers(*, cycles: int = 2) -> None:
    """Give deferred async client cleanup a chance to run before loop close.

    Some third-party SDKs schedule transport shutdown in object finalizers.
    If those objects are only garbage-collected after the event loop closes,
    asyncio logs noisy "Event loop is closed" errors from late `aclose()` tasks.

    Running a small GC + event-loop drain during shutdown keeps cleanup inside
    the active loop where those tasks can complete normally.
    """

    for _ in range(max(cycles, 1)):
        gc.collect()
        await asyncio.sleep(0)
