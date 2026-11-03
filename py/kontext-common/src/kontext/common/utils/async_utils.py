"""
Asynchronous utilities for the Kontext.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable


async def poll_until[T](
    check_fn: Callable[[], Awaitable[T | None]],
    timeout_seconds: float,
    poll_interval_seconds: float = 0.5,
) -> T | None:
    """
    Generic polling utility that waits until a condition is met or timeout occurs.

    Args:
        check_fn: Async function that returns a value when condition is met,
                 or None to continue polling.
        timeout_seconds: Maximum time to wait in seconds.
        poll_interval_seconds: Time to wait between polls in seconds.

    Returns:
        The value returned by check_fn, or None if timeout occurs.
    """
    start_time = time.time()
    while True:
        result = await check_fn()
        if result is not None:
            return result

        if time.time() - start_time > timeout_seconds:
            return None

        await asyncio.sleep(poll_interval_seconds)
