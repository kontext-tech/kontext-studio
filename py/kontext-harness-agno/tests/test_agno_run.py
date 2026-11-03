"""Unit tests for the bounded run-event queue used by the Agno stream runner.

The queue implementation is the neutral `BoundedEventQueue`
(kontext.agent.streaming); this module pins it against real Agno pause/error
event types, which only the adapter supplies.
"""

from __future__ import annotations

from agno.agent import RunErrorEvent, RunPausedEvent

from kontext.agent.streaming import BoundedEventQueue
from kontext.harness.agno.run import _is_critical_event


def _queue(maxsize: int) -> BoundedEventQueue:
    return BoundedEventQueue(maxsize=maxsize, is_critical=_is_critical_event)


def test_overflow_evicts_oldest_regular_event() -> None:
    queue = _queue(maxsize=3)
    for item in ("a", "b", "c"):
        queue.offer(item)

    queue.offer("d")

    assert list(queue._items) == ["b", "c", "d"]


def test_regular_overflow_never_evicts_a_pause_event() -> None:
    queue = _queue(maxsize=3)
    paused = RunPausedEvent(run_id="r1")
    queue.offer("a")
    queue.offer(paused)
    queue.offer("c")

    # Full; a regular event must drop the oldest regular event, not the pause.
    queue.offer("d")

    items = list(queue._items)
    assert paused in items
    assert "a" not in items
    assert "c" in items and "d" in items


def test_critical_event_drops_oldest_regular_when_full() -> None:
    queue = _queue(maxsize=2)
    queue.offer("a")
    queue.offer("b")

    queue.offer(RunErrorEvent(content="boom"))

    items = list(queue._items)
    assert any(isinstance(item, RunErrorEvent) for item in items)
    assert "a" not in items


def test_end_of_stream_sentinel_survives_overflow() -> None:
    queue = _queue(maxsize=2)
    queue.offer("a")
    queue.offer(RunPausedEvent(run_id="r1"))

    queue.offer(None)

    items = list(queue._items)
    assert items[-1] is None
    assert "a" not in items
