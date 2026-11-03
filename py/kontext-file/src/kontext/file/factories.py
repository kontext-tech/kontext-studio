"""File-domain helper functions used by transports."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from kontext.common.messaging import IQueueClient
from kontext.data import FileDataService
from kontext.storage import get_storage_provider

from .service import FileService


def create_file_service(project_id: UUID, queue_client: IQueueClient | None = None) -> FileService:
    """Create a file service with storage and optional queue wiring."""
    return FileService(
        project_id=project_id,
        storage_provider=get_storage_provider(),
        queue_client=queue_client,
    )


async def get_file_resource(project_id: UUID, file_id: UUID) -> Any | None:
    """Fetch a file record for authorization checks."""
    service = FileDataService(project_id)
    return await service.get_file_by_id_async(file_id)
