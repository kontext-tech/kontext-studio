"""Neutral streaming bridge primitives.

Ordering, buffering, and backpressure policy for run-event streaming, owned by
the neutral contract layer so every harness adapter implements the same
observable stream semantics (see docs/ai/harness-abstraction.md):

- `EventBuffer` merges small content chunks before they reach the client
  (markdown-table-safe flush boundaries).
- `BoundedEventQueue` bounds memory for abandoned consumers, keeps the
  end-of-stream sentinel last, and never evicts critical events (pause/error)
  — a pause can never be lost behind a burst of stream events.

Adapters may plug their own producer threading into `BoundedEventQueue.offer`
(`call_soon_threadsafe` offloads, direct async producers, ...); the consumer
side policy is identical for every harness.
"""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from kontext.schema import (
    EventData,
    ReasoningEventData,
    RunContentEventData,
    RunEvent,
    SimpleRunEvent,
)

__all__ = ["BoundedEventQueue", "EventBuffer"]

_logger = logging.getLogger(__name__)


@dataclass
class EventBuffer:
    """Buffer for optimizing RunContentEvent streaming."""

    # Configuration
    max_buffer_size: int = 512  # Characters to buffer before flushing
    enabled: bool = True

    # Internal state
    _buffered_events: list[SimpleRunEvent] = field(default_factory=list)
    _buffered_content: str = ""
    _buffered_reasoning: str = ""
    _current_event_type: RunEvent | None = None

    def should_buffer(self, event: SimpleRunEvent) -> bool:
        """Check if event should be buffered."""
        if not self.enabled:
            return False

        # Buffer both RunContent and ReasoningStep events
        if event.event_type not in (RunEvent.RUNCONTENT, RunEvent.REASONINGSTEP):
            return False

        has_content = False
        has_reasoning = False

        # In RunContent, 'content' is normal output
        if event.event_type == RunEvent.RUNCONTENT:
            has_content = event.content is not None

        if event.reasoning:
            has_reasoning = True

        # Check for content in ReasoningStep
        if event.event_data and (
            isinstance(event.event_data.root, ReasoningEventData) and event.event_data.root.content
        ):
            has_reasoning = True

        # Fallback for ReasoningStep content
        if event.event_type == RunEvent.REASONINGSTEP and event.content:
            has_reasoning = True

        return has_content or has_reasoning

    def add_event(self, event: SimpleRunEvent) -> SimpleRunEvent | None:
        """
        Add event to buffer. Returns event if buffer should flush, None otherwise.
        """
        if not self.should_buffer(event):
            # Flush any buffered content first, then return the new event
            flushed_event = self.flush()
            return flushed_event or event

        # Buffer the content
        if event.event_type == RunEvent.RUNCONTENT and event.content:
            self._buffered_content += event.content

        # Buffer the reasoning content
        if event.reasoning:
            self._buffered_reasoning += event.reasoning
        elif (
            event.event_data
            and isinstance(event.event_data.root, ReasoningEventData)
            and event.event_data.root.content
        ):
            self._buffered_reasoning += event.event_data.root.content

        # Fallback for ReasoningStep content
        if (
            event.event_type == RunEvent.REASONINGSTEP
            and event.content
            and not (
                event.event_data
                and isinstance(event.event_data.root, ReasoningEventData)
                and event.event_data.root.content == event.content
            )
        ):
            self._buffered_reasoning += event.content

        self._buffered_events.append(event)

        # Check if we should flush due to size (sum of both content types)
        total_buffered = len(self._buffered_content) + len(self._buffered_reasoning)
        if total_buffered >= self.max_buffer_size:
            # CRITICAL: Only flush if last character is a newline to avoid breaking markdown tables
            # Markdown tables require complete lines (rows end with \n)
            last_char_content = self._buffered_content[-1] if self._buffered_content else ""
            last_char_reasoning = self._buffered_reasoning[-1] if self._buffered_reasoning else ""

            # Flush if we're at a line boundary OR buffer is significantly over limit (prevent unbounded growth)
            if (
                last_char_content == "\n"
                or last_char_reasoning == "\n"
                or total_buffered >= self.max_buffer_size * 2
            ):
                return self.flush()

        return None

    def flush(self) -> SimpleRunEvent | None:
        """Flush buffered content and return consolidated event."""
        if not self._buffered_content and not self._buffered_reasoning:
            return None

        # Create consolidated event from buffered content
        # Use the event_data from the last event as a base, but update content-specific fields
        last_event_data = self._buffered_events[-1].event_data if self._buffered_events else None

        new_event_data = None
        if last_event_data and isinstance(last_event_data.root, RunContentEventData):
            # Clone and update
            root = RunContentEventData(content_type=last_event_data.root.content_type)
            new_event_data = EventData(root=root)
        elif self._buffered_reasoning:
            # Create new if it didn't exist but we have reasoning
            root = RunContentEventData(
                content_type="str",  # Default to str (Agno consistent)
            )
            new_event_data = EventData(root=root)

        consolidated_event = SimpleRunEvent(
            event_type=RunEvent.RUNCONTENT,
            content=self._buffered_content if self._buffered_content else None,
            reasoning=self._buffered_reasoning if self._buffered_reasoning else None,
            event_data=new_event_data or last_event_data,
        )

        # Reset buffer
        self._buffered_events.clear()
        self._buffered_content = ""
        self._buffered_reasoning = ""

        return consolidated_event

    def flush_on_event_type_change(self, new_event_type: RunEvent) -> SimpleRunEvent | None:
        """Flush buffer if event type changes."""
        if self._current_event_type != new_event_type and (
            self._buffered_content or self._buffered_reasoning
        ):
            self._current_event_type = new_event_type
            return self.flush()
        self._current_event_type = new_event_type
        return None


class BoundedEventQueue:
    """Bounded queue of run events between a producer and the consumer loop.

    ``offer`` runs on the consumer loop (``call_soon_threadsafe`` for
    thread-offloaded producers or a direct async producer) and ``take`` awaits
    on the same loop, so the deque/Event state is single-loop confined.
    ``deque(maxlen=...)`` evicts oldest-first when full, which bounds memory
    for an abandoned consumer; overflow is reported once per drain. The
    end-of-stream sentinel is appended last, so eviction only ever drops
    regular events — the consumer can never wait for a completion that was
    discarded. When the queue is full and the incoming event is critical (see
    ``is_critical``), the oldest regular event is dropped instead so a pause
    can never be lost behind a burst of stream events.
    """

    def __init__(
        self,
        *,
        maxsize: int = 10_000,
        is_critical: Callable[[Any], bool] | None = None,
    ) -> None:
        self._items: deque[Any] = deque(maxlen=maxsize)
        self._activity = asyncio.Event()
        self._dropped = 0
        self._is_critical = is_critical

    def offer(self, item: Any) -> None:
        """Enqueue *item* (invoked on the consumer loop)."""
        if len(self._items) == self._items.maxlen:
            self._dropped += 1
            if self._is_critical and self._is_critical(item):
                for index, existing in enumerate(self._items):
                    if self._is_critical(existing):
                        continue
                    del self._items[index]
                    break
        self._items.append(item)
        self._activity.set()

    async def take(self, poll_timeout: float = 1.0) -> Any:
        """Await the next event; raises ``TimeoutError`` while still empty."""
        while not self._items:
            self._activity.clear()
            await asyncio.wait_for(self._activity.wait(), timeout=poll_timeout)
        item = self._items.popleft()
        if self._dropped:
            _logger.warning(
                "Run event queue overflow: dropped %d buffered event(s) "
                "(consumer too slow or disconnected).",
                self._dropped,
            )
            self._dropped = 0
        return item
