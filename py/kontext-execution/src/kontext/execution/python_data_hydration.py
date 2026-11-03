"""Shared hydration of scoped data-id payloads for managed Python jobs.

Both managed Python jobs (session scripts and notebook blocks) expose SQL
results to user code through ``kontext.load_data(data_id)``. For large results
the persisted file holds only a bounded preview next to a companion row store;
hydrating the file content directly would silently hand the kernel a truncated
view, so both jobs resolve the *entire* result (offset 0, no limit) here.

Data sources that cannot be hydrated are skipped and reported, so a bad id
surfaces as the kernel's "Data '<id>' is not available." error at load time
instead of failing the whole job for unrelated data.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID


async def hydrate_data_payloads(
    *,
    project_id: UUID | str,
    data_sources: dict[str, str],
    file_service: Any,
) -> tuple[dict[str, str], list[str]]:
    """Build ``data_id -> InlineData JSON`` payloads for kernel host calls.

    Returns the payloads plus the list of data ids that could not be hydrated
    (missing file, unreadable companion store, or non-data file).
    """
    payloads: dict[str, str] = {}
    skipped: list[str] = []
    # Aliases and durable ids can both point at one persisted file; hydrate
    # each file at most once and share the payload across its names.
    hydrated_files: dict[str, str] = {}
    for data_id, file_id in data_sources.items():
        if file_id in hydrated_files:
            payloads[data_id] = hydrated_files[file_id]
            continue
        try:
            inline_data = await file_service.get_inline_data_rows(
                project_id,
                file_id,
                offset=0,
                limit=None,
            )
        except Exception:
            skipped.append(data_id)
            continue
        payload = inline_data.model_dump_json(exclude_none=True, by_alias=True)
        payloads[data_id] = hydrated_files[file_id] = payload
    return payloads, skipped
