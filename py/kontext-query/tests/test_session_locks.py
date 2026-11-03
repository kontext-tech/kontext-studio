from __future__ import annotations

import asyncio
import threading
from collections.abc import Callable

import pytest

from kontext.common.query.session_locks import (
    get_session_lock,
    session_execution_lock,
)


@pytest.mark.asyncio
async def test_session_lock_serializes_same_session() -> None:
    order: list[str] = []
    entered = asyncio.Event()
    release = asyncio.Event()

    async def first() -> None:
        async with session_execution_lock("session-1"):
            order.append("first:enter")
            entered.set()
            await release.wait()
            order.append("first:exit")

    async def second() -> None:
        await entered.wait()
        async with session_execution_lock("session-1"):
            order.append("second:enter")

    first_task = asyncio.create_task(first())
    second_task = asyncio.create_task(second())

    await asyncio.sleep(0.01)
    # The second holder must not enter while the first is still running.
    assert order == ["first:enter"]

    release.set()
    await asyncio.gather(first_task, second_task)
    assert order == ["first:enter", "first:exit", "second:enter"]


@pytest.mark.asyncio
async def test_session_lock_allows_different_sessions_concurrently() -> None:
    order: list[str] = []
    entered = asyncio.Event()
    release = asyncio.Event()

    async def first() -> None:
        async with session_execution_lock("session-a"):
            order.append("a:enter")
            entered.set()
            await release.wait()

    async def second() -> None:
        await entered.wait()
        async with session_execution_lock("session-b"):
            order.append("b:enter")

    first_task = asyncio.create_task(first())
    second_task = asyncio.create_task(second())

    await asyncio.wait_for(second_task, timeout=1)
    assert order == ["a:enter", "b:enter"]

    release.set()
    await first_task


def test_get_session_lock_is_stable_within_a_loop() -> None:
    async def _check() -> None:
        assert get_session_lock("x") is get_session_lock("x")
        assert get_session_lock("x") is not get_session_lock("y")

    asyncio.run(_check())


def _run_cycles_on_dedicated_loop(
    iterations: int,
    violations: list[str],
    is_in_critical: Callable[[str], bool],
    enter_critical: Callable[[str], None],
    exit_critical: Callable[[str], None],
) -> None:
    """Run *iterations* critical sections on a fresh loop, in this thread.

    Mirrors production topology: the API server loop and each agent run have
    their own event loop, on separate threads.
    """

    async def _worker() -> None:
        key = "shared-session"
        for _ in range(iterations):
            async with session_execution_lock(key):
                if is_in_critical(key):
                    violations.append("overlap")
                    return
                enter_critical(key)
                await asyncio.sleep(0.001)
                exit_critical(key)

    loop = asyncio.new_event_loop()
    try:
        loop.run_until_complete(_worker())
    finally:
        loop.close()


def test_session_lock_excludes_across_loops() -> None:
    """Loops from different threads must not share a session concurrently.

    Regression: the lock table used to replace the asyncio.Lock whenever a
    different loop touched the key, silently dropping mutual exclusion between
    the API server loop and per-run agent thread loops.
    """
    counters: dict[str, int] = {}
    guard = threading.Lock()

    def _in_critical(key: str) -> bool:
        return counters.get(key, 0) > 0

    def _enter_critical(key: str) -> None:
        with guard:
            counters[key] = counters.get(key, 0) + 1

    def _exit_critical(key: str) -> None:
        with guard:
            counters[key] -= 1

    violations: list[str] = []
    cycles = 25
    threads = [
        threading.Thread(
            target=_run_cycles_on_dedicated_loop,
            args=(cycles, violations, _in_critical, _enter_critical, _exit_critical),
        )
        for _ in range(3)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
        assert not thread.is_alive()
    assert violations == []
    assert counters == {"shared-session": 0}


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_leak_the_thread_lock() -> None:
    from kontext.common.query.session_locks import _get_thread_lock

    key = "cancel-me"
    lock = _get_thread_lock(key)
    # Another loop (e.g. the API server loop) already holds the execution.
    assert lock.acquire(blocking=False)

    async def _waiter() -> None:
        async with session_execution_lock(key):
            pass  # pragma: no cover - must never be reached

    waiter_task = asyncio.create_task(_waiter())
    await asyncio.sleep(0.05)  # let it reach the polling loop
    waiter_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiter_task

    # The cancelled waiter neither holds nor steals the thread lock.
    lock.release()
    assert lock.acquire(blocking=False)
    lock.release()
