"""
Test EventBuffer with markdown table scenarios to verify newline boundary handling.
"""

from kontext.agent.streaming import EventBuffer
from kontext.schema import EventData, RunContentEventData, RunEvent, SimpleRunEvent


def test_markdown_table_not_split_mid_line():
    """Test that markdown tables are not split in the middle of a line."""
    buffer = EventBuffer(max_buffer_size=50, enabled=True)

    # Simulate streaming a markdown table
    # Each row should end with \n to be valid markdown
    table_header = "| Column A | Column B |\n"  # 24 chars
    table_separator = "|----------|----------|\n"  # 24 chars
    table_row_1 = "| Value 1  | Value 2  |\n"  # 24 chars (total: 72 chars)

    # Add header (24 chars)
    event1 = SimpleRunEvent(
        event_type=RunEvent.RUNCONTENT,
        content=table_header,
        event_data=EventData(root=RunContentEventData(content_type="str")),
    )
    result1 = buffer.add_event(event1)
    assert result1 is None, "Should not flush yet - under limit"

    # Add separator (24 chars, total: 48 chars - just under 50 limit)
    event2 = SimpleRunEvent(
        event_type=RunEvent.RUNCONTENT,
        content=table_separator,
        event_data=EventData(root=RunContentEventData(content_type="str")),
    )
    result2 = buffer.add_event(event2)
    assert result2 is None, "Should not flush yet - under limit"

    # Add first row (24 chars, total: 72 chars - over 50 limit)
    event3 = SimpleRunEvent(
        event_type=RunEvent.RUNCONTENT,
        content=table_row_1,
        event_data=EventData(root=RunContentEventData(content_type="str")),
    )
    result3 = buffer.add_event(event3)

    # Should flush because:
    # 1. Total is 72 > 50 (max_buffer_size)
    # 2. Last character is '\n' (line boundary)
    assert result3 is not None, "Should flush at line boundary after exceeding limit"
    assert result3.content == table_header + table_separator + table_row_1
    assert result3.content.endswith("\n"), "Flushed content should end with newline"


def test_incomplete_table_row_waits_for_newline():
    """Test that incomplete table rows wait for newline before flushing."""
    buffer = EventBuffer(max_buffer_size=30, enabled=True)

    # Simulate streaming an incomplete row that doesn't end with \n
    incomplete_row = "| Column A | Column B | Column"  # 31 chars, no trailing \n

    event = SimpleRunEvent(
        event_type=RunEvent.RUNCONTENT,
        content=incomplete_row,
        event_data=EventData(root=RunContentEventData(content_type="str")),
    )
    result = buffer.add_event(event)

    # Should NOT flush even though 31 > 30 because last char is not '\n'
    # Will wait for next event or until buffer reaches 2x limit (60)
    assert result is None, "Should not flush - no newline boundary"

    # Add the rest of the row with newline
    row_end = " C |\n"
    event2 = SimpleRunEvent(
        event_type=RunEvent.RUNCONTENT,
        content=row_end,
        event_data=EventData(root=RunContentEventData(content_type="str")),
    )
    result2 = buffer.add_event(event2)

    # Should flush now because we have a newline
    assert result2 is not None, "Should flush after newline"
    assert result2.content == incomplete_row + row_end
    assert result2.content.endswith("\n")


def test_buffer_prevents_unbounded_growth():
    """Test that buffer flushes at 2x limit to prevent unbounded growth."""
    buffer = EventBuffer(max_buffer_size=20, enabled=True)

    # Add content that exceeds 2x limit without newlines
    long_content = "a" * 50  # 50 chars, no newlines, exceeds 2x limit (40)

    event = SimpleRunEvent(
        event_type=RunEvent.RUNCONTENT,
        content=long_content,
        event_data=EventData(root=RunContentEventData(content_type="str")),
    )
    result = buffer.add_event(event)

    # Should flush because 50 >= 40 (2x limit) to prevent unbounded growth
    assert result is not None, "Should flush at 2x limit to prevent unbounded growth"
    assert result.content == long_content


def test_reasoning_content_newline_boundary():
    """Test that reasoning content also respects newline boundaries."""
    buffer = EventBuffer(max_buffer_size=30, enabled=True)

    # Add reasoning content ending with newline
    reasoning_1 = "Thinking about the problem...\n"  # 31 chars with \n

    event = SimpleRunEvent(
        event_type=RunEvent.RUNCONTENT,
        reasoning=reasoning_1,
        event_data=EventData(root=RunContentEventData(content_type="str")),
    )
    result = buffer.add_event(event)

    # Should flush because 31 > 30 and last char is '\n'
    assert result is not None, "Should flush reasoning at newline boundary"
    assert result.reasoning == reasoning_1
    assert result.reasoning.endswith("\n")


def test_mixed_content_and_reasoning_newline_check():
    """Test that newline check considers both content and reasoning."""
    buffer = EventBuffer(max_buffer_size=20, enabled=True)

    # Add content without newline (15 chars)
    event1 = SimpleRunEvent(
        event_type=RunEvent.RUNCONTENT,
        content="Some content ok",  # 15 chars, no \n
        event_data=EventData(root=RunContentEventData(content_type="str")),
    )
    result1 = buffer.add_event(event1)
    assert result1 is None

    # Add reasoning with newline (10 chars, total: 25 > 20)
    event2 = SimpleRunEvent(
        event_type=RunEvent.RUNCONTENT,
        reasoning="thinking\n",  # 9 chars with \n, total 24 > 20
        event_data=EventData(root=RunContentEventData(content_type="str")),
    )
    result2 = buffer.add_event(event2)

    # Should flush because total > limit and reasoning ends with \n
    assert result2 is not None, "Should flush when reasoning has newline"
    assert result2.content == "Some content ok"
    assert result2.reasoning == "thinking\n"
