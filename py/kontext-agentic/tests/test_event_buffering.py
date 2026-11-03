"""
Test script to validate event buffering optimization.
"""

import asyncio

from kontext.agent.streaming import EventBuffer
from kontext.schema import (
    EventData,
    ReasoningEventData,
    RunContentEventData,
    RunEvent,
    SimpleRunEvent,
)


async def test_event_buffering():
    """Test the EventBuffer functionality."""

    # Create buffer with larger size for testing concatenation
    buffer = EventBuffer(max_buffer_size=50, enabled=True)

    # Test 1: Buffer consecutive RunContentEvents
    events = [
        SimpleRunEvent(event_type=RunEvent.RUNCONTENT, content="Hello "),
        SimpleRunEvent(event_type=RunEvent.RUNCONTENT, content="world "),
        SimpleRunEvent(event_type=RunEvent.RUNCONTENT, content="from "),
        SimpleRunEvent(event_type=RunEvent.RUNCONTENT, content="AI!"),
    ]

    buffered_results = []
    for i, event in enumerate(events):
        content_len = len(event.content) if event.content else 0
        print(f"Processing event {i}: '{event.content}' (len={content_len})")
        result = buffer.add_event(event)
        if result:
            result_len = len(result.content) if result.content else 0
            print(f"  -> Flushed: '{result.content}' (len={result_len})")
            buffered_results.append(result)
        else:
            print("  -> Buffered (not flushed)")

    # Manually flush any remaining buffered content
    final_flush = buffer.flush()
    if final_flush:
        buffered_results.append(final_flush)
        print(f"Final flush: '{final_flush.content}'")

    print(f"\nFinal results: {len(buffered_results)} events")
    for i, result in enumerate(buffered_results):
        print(f"Result {i}: '{result.content}'")

    # Should have one consolidated event with all content
    assert len(buffered_results) == 1
    res = buffered_results[0]
    assert res is not None
    assert res.content == "Hello world from AI!"
    print("✓ Test 1 passed: Consecutive RunContentEvents consolidated")

    # Test 2: Event type change triggers flush
    buffer2 = EventBuffer(max_buffer_size=100, enabled=True)

    # Add some content events
    buffer2.add_event(SimpleRunEvent(event_type=RunEvent.RUNCONTENT, content="Buffered "))
    buffer2.add_event(SimpleRunEvent(event_type=RunEvent.RUNCONTENT, content="content "))

    # Different event type should trigger flush
    flush_result = buffer2.flush_on_event_type_change(RunEvent.TOOLCALLSTARTED)
    assert flush_result is not None
    assert flush_result.content == "Buffered content "
    print("✓ Test 2 passed: Event type change triggers buffer flush")

    # Test 3: Non-buffering events pass through immediately
    buffer3 = EventBuffer(max_buffer_size=100, enabled=True)

    tool_event = SimpleRunEvent(event_type=RunEvent.TOOLCALLSTARTED, content="Tool started")
    result = buffer3.add_event(tool_event)

    # Should return the event immediately (not buffer it)
    assert result == tool_event
    print("✓ Test 3 passed: Non-buffering events pass through immediately")

    # Test 4: Buffer size limit triggers flush
    buffer4 = EventBuffer(max_buffer_size=5, enabled=True)  # Very small buffer

    # Add content that exceeds buffer size
    result = buffer4.add_event(
        SimpleRunEvent(event_type=RunEvent.RUNCONTENT, content="Hello world!")
    )
    assert result is not None
    assert result.content == "Hello world!"
    print("✓ Test 4 passed: Buffer size limit triggers flush")

    print("\n🎉 All tests passed! Event buffering optimization is working correctly.")


async def test_reasoning_buffering():
    """Test the EventBuffer functionality with reasoning content."""

    # Create buffer
    buffer = EventBuffer(max_buffer_size=50, enabled=True)

    # Test: Buffer consecutive RunContentEvents with reasoning
    events = [
        SimpleRunEvent(
            event_type=RunEvent.RUNCONTENT,
            reasoning="Thinking ",
            event_data=EventData(root=RunContentEventData(content_type="str")),
        ),
        SimpleRunEvent(
            event_type=RunEvent.RUNCONTENT,
            reasoning="about ",
            event_data=EventData(root=RunContentEventData(content_type="str")),
        ),
        SimpleRunEvent(
            event_type=RunEvent.RUNCONTENT,
            reasoning="Life...",
            event_data=EventData(root=RunContentEventData(content_type="str")),
        ),
    ]

    buffered_results = []
    for event in events:
        result = buffer.add_event(event)
        if result:
            buffered_results.append(result)

    # Manually flush
    final_flush = buffer.flush()
    if final_flush:
        buffered_results.append(final_flush)

    assert len(buffered_results) == 1
    res = buffered_results[0]
    assert res.reasoning == "Thinking about Life..."
    assert res.content is None
    print("✓ Test: ReasoningContent consolidated")

    # Test: Mixed content and reasoning
    buffer_mixed = EventBuffer(max_buffer_size=50, enabled=True)
    events_mixed = [
        SimpleRunEvent(
            event_type=RunEvent.RUNCONTENT,
            content="Hello ",
            reasoning="Start ",
            event_data=EventData(root=RunContentEventData(content_type="str")),
        ),
        SimpleRunEvent(
            event_type=RunEvent.RUNCONTENT,
            content="World",
            reasoning="End",
            event_data=EventData(root=RunContentEventData(content_type="str")),
        ),
    ]

    for event in events_mixed:
        buffer_mixed.add_event(event)

    mixed_flush = buffer_mixed.flush()
    assert mixed_flush is not None
    assert mixed_flush.content == "Hello World"
    assert mixed_flush.reasoning == "Start End"
    print("✓ Test: Mixed Content and Reasoning consolidated")


async def test_reasoning_step_buffering():
    """Test the EventBuffer functionality with ReasoningStep events."""

    # Create buffer
    buffer = EventBuffer(max_buffer_size=50, enabled=True)

    # Test: Buffer consecutive ReasoningStep events
    events = [
        SimpleRunEvent(event_type=RunEvent.REASONINGSTEP, content="Step 1 "),
        SimpleRunEvent(
            event_type=RunEvent.REASONINGSTEP,
            event_data=EventData(root=ReasoningEventData(content="Step 2")),
        ),
    ]

    for event in events:
        buffer.add_event(event)

    res = buffer.flush()
    assert res is not None
    assert res.event_type == RunEvent.RUNCONTENT
    assert res.reasoning == "Step 1 Step 2"
    print("✓ Test: ReasoningStep consolidated into RunContent")


async def main():
    await test_event_buffering()
    await test_reasoning_buffering()
    await test_reasoning_step_buffering()


if __name__ == "__main__":
    asyncio.run(main())
