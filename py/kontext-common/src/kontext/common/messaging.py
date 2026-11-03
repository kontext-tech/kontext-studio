"""
Cloud-agnostic queue messaging contracts shared across Kontext packages.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


@dataclass
class QueueMessage:
    """
    Cloud-agnostic queue message representation.

    Attributes:
        message_id: Unique message identifier
        body: Message content (string)
        receipt_handle: Provider-specific handle for delete/update operations
        dequeue_count: Number of times message has been received
        inserted_at: When message was added to queue
        expires_at: When message will expire (if applicable)
        pop_receipt: Secondary receipt/token for some providers (e.g., Azure)
    """

    message_id: str
    body: str
    receipt_handle: str
    dequeue_count: int = 0
    inserted_at: datetime | None = None
    expires_at: datetime | None = None
    pop_receipt: str | None = None


class IQueueClient(Protocol):
    """
    Protocol defining the interface for queue client implementations.
    """

    async def send_message(self, message: str) -> str: ...

    def receive_messages(
        self, max_messages: int, visibility_timeout: int
    ) -> AsyncIterator[QueueMessage]: ...

    async def delete_message(self, message_id: str, receipt_handle: str) -> None: ...

    async def update_message(
        self, message_id: str, receipt_handle: str, visibility_timeout: int
    ) -> str: ...

    async def close(self) -> None: ...
