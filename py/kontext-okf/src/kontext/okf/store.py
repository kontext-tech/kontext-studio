"""Durable, lake-native store for OKF concepts.

Concepts are persisted as **real OKF bundle markdown files** under the project's
``.okf`` system folder (e.g. ``.okf/tables/bronze.orders.md``). This means the
on-disk storage format *is* the OKF exchange format: what you store is what you
export/import, with zero translation. Files are human-readable and editable in
any text editor, and the folder is hidden from the file browser UI via the
``SYSTEM_MANAGED_PROJECT_FILE_PREFIXES`` convention (alongside ``.lakehouse``
and ``.knowledge``).

This is the single durable home for all OKF concepts — both machine-generated
(from the enrichment job) and, in future, human-authored (from a knowledge
editor UI). Both paths write here and both are projected into the unified
knowledge index via :meth:`CatalogIndexService.index_okf_concepts`.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from .bundle import OkfBundle, load_bundle, write_bundle
from .concept import OkfConcept

logger = logging.getLogger(__name__)


class OkfConceptStore:
    """A durable, OKF-bundle-backed store of concepts for one project.

    Each concept is stored as a ``*.md`` file inside the bundle directory, keyed
    by its OKF concept id (the file path within the bundle, sans ``.md``).
    Upserts replace an existing concept with the same id (so re-running the
    enrichment job refreshes rather than duplicates). The store is safe for
    single-writer access (the enrichment job); concurrent writers are not
    supported by design.
    """

    def __init__(self, bundle_dir: str | os.PathLike[str]) -> None:
        self._dir = Path(bundle_dir)

    @classmethod
    def for_project(cls, project_id: str) -> OkfConceptStore:
        """Build a store at the conventional project ``.okf`` storage location."""
        # Late import to avoid a hard dependency on kontext-common at module
        # load time; this keeps the okf package importable in isolation for
        # unit tests that construct the store from an explicit path.
        from kontext.common.utils.file_storage import (
            OKF_PROJECT_FILE_PREFIX,
            get_project_storage_path,
        )

        return cls(get_project_storage_path(project_id, OKF_PROJECT_FILE_PREFIX))

    @property
    def path(self) -> Path:
        """The absolute path of the backing bundle directory."""
        return self._dir

    def list_concepts(self) -> list[OkfConcept]:
        """Return all stored concepts. Returns ``[]`` if none exist yet."""
        if not self._dir.is_dir():
            return []
        try:
            bundle = load_bundle(self._dir)
        except Exception as exc:
            logger.warning("Failed to read OKF concept store %s: %s", self._dir, exc)
            return []
        return bundle.to_list()

    def get_concept(self, concept_id: str) -> OkfConcept | None:
        """Return a single concept by id, or ``None`` if not present."""
        for concept in self.list_concepts():
            if concept.id == concept_id:
                return concept
        return None

    def upsert_concepts(self, concepts: list[OkfConcept]) -> int:
        """Insert or replace concepts, keyed by id. Returns the count stored.

        Reads the existing bundle (if any), merges the new concepts by id, and
        rewrites the whole bundle. This is simple and correct for the expected
        corpus size (hundreds to low-thousands of concepts per project).
        """
        if not concepts:
            return 0
        existing = {concept.id: concept for concept in self.list_concepts()}
        for concept in concepts:
            existing[concept.id] = concept
        bundle = OkfBundle(name=self._dir.name, concepts=list(existing.values()))
        write_bundle(bundle, self._dir)
        return len(concepts)

    def clear(self) -> int:
        """Delete all stored concepts. Returns the count removed."""
        count = len(self.list_concepts())
        if count and self._dir.exists():
            import shutil

            shutil.rmtree(self._dir, ignore_errors=True)
        return count
