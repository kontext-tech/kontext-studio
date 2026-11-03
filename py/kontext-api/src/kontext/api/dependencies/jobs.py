"""Job-related dependencies for the Kontext API."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from uuid import uuid4

from fastapi import Depends

from kontext.common.messaging import IQueueClient, QueueMessage
from kontext.runtime.local.config import is_local_mode

logger = logging.getLogger(__name__)


class LocalPollingQueueClient(IQueueClient):
    """Queue client used by local mode when a polling worker handles queued runs.

    In console/local mode, job runs are persisted with ``Queued`` status and the
    embedded worker polls the database directly. There is no broker to push a
    message to, so ``send_message`` intentionally becomes a lightweight no-op.
    """

    async def send_message(self, message: str) -> str:
        _ = message
        return str(uuid4())

    async def receive_messages(
        self, max_messages: int, visibility_timeout: int
    ) -> AsyncIterator[QueueMessage]:
        _ = (max_messages, visibility_timeout)
        if False:
            yield QueueMessage(message_id="", body="", receipt_handle="")

    async def delete_message(self, message_id: str, receipt_handle: str) -> None:
        _ = (message_id, receipt_handle)

    async def update_message(
        self, message_id: str, receipt_handle: str, visibility_timeout: int
    ) -> str:
        _ = (message_id, receipt_handle, visibility_timeout)
        return str(uuid4())

    async def close(self) -> None:
        return None


_local_queue_client: IQueueClient | None = None


async def get_queue_client() -> IQueueClient | None:
    """
    Get the queue client for local job scheduling.

    In local console mode, return a lightweight queue client because the
    embedded worker polls queued job runs from SQLite directly. In cloud mode,
    no queue provider is configured here yet.
    """
    global _local_queue_client

    if is_local_mode():
        if _local_queue_client is None:
            _local_queue_client = LocalPollingQueueClient()
        return _local_queue_client

    logger.debug("Queue client requested - no provider configured, returning None")
    return None


QUEUE_CLIENT_DEP = Depends(get_queue_client)
"""The single shared queue-client dependency; routers must not redefine it."""
