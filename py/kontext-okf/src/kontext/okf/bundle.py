"""OKF bundle directory I/O.

An OKF *bundle* is a self-contained directory of concept markdown files. The
concept id is the file's path within the bundle (with the ``.md`` suffix
removed), per the OKF spec. This module reads/writes a bundle directory and is
the unit of distribution for portable knowledge exchange.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

from .concept import OkfConcept
from .frontmatter import concept_from_frontmatter, concept_to_frontmatter

logger = logging.getLogger(__name__)

#: File suffix for OKF concept files.
_CONCEPT_SUFFIX = ".md"

#: Reserved filenames that carry directory structure/history, not concepts
#: (OKF spec §3.1). They are never parsed as concept documents.
_RESERVED_FILENAMES = frozenset({"index.md", "log.md"})

#: Root ``index.md`` filename.
_INDEX_FILENAME = "index.md"

#: OKF version declared in the root ``index.md`` frontmatter (OKF spec §12).
_OKF_VERSION = "0.2"


class OkfBundleReadError(RuntimeError):
    """Raised when a bundle directory cannot be read or parsed."""


class OkfBundle:
    """An in-memory OKF bundle: a named collection of concepts.

    Lightweight value object. Use :func:`load_bundle` to read a directory and
    :func:`write_bundle` to materialize one. Concepts are keyed by their OKF
    concept id (the file path within the bundle, sans ``.md``).
    """

    def __init__(self, name: str, concepts: list[OkfConcept] | None = None) -> None:
        self.name = name
        self.concepts: dict[str, OkfConcept] = {}
        for concept in concepts or []:
            self.concepts[concept.id or "concepts/untitled"] = concept

    def __len__(self) -> int:
        return len(self.concepts)

    def __iter__(self) -> Iterator[OkfConcept]:
        return iter(self.concepts.values())

    def add(self, concept: OkfConcept) -> None:
        self.concepts[concept.id or "concepts/untitled"] = concept

    def get(self, concept_id: str) -> OkfConcept | None:
        return self.concepts.get(concept_id)

    def to_list(self) -> list[OkfConcept]:
        return list(self.concepts.values())


def load_bundle(bundle_dir: str | Path) -> OkfBundle:
    """Read an OKF bundle directory into an :class:`OkfBundle`.

    Every ``*.md`` file under the directory (recursively) is parsed as a
    concept. The concept id is the file's path relative to ``bundle_dir`` with
    the ``.md`` suffix removed (POSIX-separated), matching the OKF spec.

    Raises :class:`OkfBundleReadError` if the directory is missing or a file
    fails to parse.
    """
    root = Path(bundle_dir)
    if not root.is_dir():
        raise OkfBundleReadError(f"Bundle directory not found: {root}")

    bundle = OkfBundle(name=root.name)
    for path in sorted(root.rglob(f"*{_CONCEPT_SUFFIX}")):
        if path.name in _RESERVED_FILENAMES:
            # ``index.md`` / ``log.md`` are reserved structural files, not
            # concepts (OKF spec §3.1); skip them entirely.
            continue
        relative = path.relative_to(root).with_suffix("")
        concept_id = relative.as_posix()
        try:
            text = path.read_text(encoding="utf-8")
            concept = concept_from_frontmatter(text)
        except (OSError, ValueError) as exc:
            raise OkfBundleReadError(f"Failed to read OKF concept {path}: {exc}") from exc
        # Prefer the filesystem-derived concept id (the OKF-defined identity)
        # when a concept does not declare its own stable ``id``.
        if not concept.id:
            concept = concept.model_copy(update={"id": concept_id})
        bundle.add(concept)
    logger.debug("Loaded OKF bundle %s with %d concepts", root, len(bundle))
    return bundle


def write_bundle(bundle: OkfBundle, bundle_dir: str | Path, *, write_index: bool = True) -> Path:
    """Materialize an :class:`OkfBundle` to a directory of markdown files.

    Returns the written directory path. Parent directories are created. Each
    concept becomes ``<bundle_dir>/<concept_id>.md``.

    When ``write_index`` is true (the default) a progressive-disclosure
    ``index.md`` is generated for the bundle root and every subdirectory, per
    OKF §8. The root ``index.md`` declares ``okf_version`` (§12).
    """
    root = Path(bundle_dir)
    root.mkdir(parents=True, exist_ok=True)
    for concept in bundle:
        # concept ids use POSIX separators; map them to the local filesystem.
        # We append ``.md`` rather than ``with_suffix`` because concept ids can
        # legitimately contain dots (e.g. ``bronze.orders``) which ``with_suffix``
        # would misinterpret as a file extension and clobber.
        concept_id = concept.id or "concepts/untitled"
        id_parts = concept_id.split("/")
        target = root.joinpath(*id_parts).with_name(id_parts[-1] + _CONCEPT_SUFFIX)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(concept_to_frontmatter(concept), encoding="utf-8")

    if write_index:
        _write_index_files(bundle, root)

    logger.debug("Wrote OKF bundle %s with %d concepts", root, len(bundle))
    return root


def _write_index_files(bundle: OkfBundle, root: Path) -> None:
    """Generate ``index.md`` for the root and every concept subdirectory (§8).

    Each index groups its directory's own concept files (links to files) and
    its immediate subdirectories (links to their ``index.md``). Descriptions
    come from each concept's frontmatter.
    """
    # Group concepts by the directory that directly holds them.
    by_directory: dict[tuple[str, ...], list[OkfConcept]] = {}
    for concept in bundle:
        concept_id = concept.id or "concepts/untitled"
        parts = concept_id.split("/")
        directory = tuple(parts[:-1])
        by_directory.setdefault(directory, []).append(concept)

    # Every directory that holds a concept, plus all ancestor directories, gets
    # an index so the tree is navigable at each level.
    directories: set[tuple[str, ...]] = {()}
    for directory in by_directory:
        for depth in range(len(directory) + 1):
            directories.add(directory[:depth])

    for directory in directories:
        target = root.joinpath(*directory, _INDEX_FILENAME)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            _render_index(directory, by_directory, is_root=not directory),
            encoding="utf-8",
        )


def _render_index(
    directory: tuple[str, ...],
    by_directory: dict[tuple[str, ...], list[OkfConcept]],
    *,
    is_root: bool,
) -> str:
    concepts = sorted(by_directory.get(directory, []), key=lambda c: c.id or "")

    # Immediate child subdirectories (non-empty ones only).
    child_dirs = sorted(
        {
            d[len(directory)]
            for d in by_directory
            if len(d) > len(directory) and d[: len(directory)] == directory
        }
    )

    lines: list[str] = []
    if is_root:
        # OKF §8/§12: the root index.md MAY declare the targeted version.
        lines.extend(["---", f'okf_version: "{_OKF_VERSION}"', "---", ""])

    if child_dirs:
        lines.append("# Subdirectories")
        lines.append("")
        for name in child_dirs:
            child = (*directory, name)
            description = _directory_description(by_directory.get(child, []))
            suffix = f" - {description}" if description else ""
            lines.append(f"* [{name}]({name}/{_INDEX_FILENAME}){suffix}")
        lines.append("")

    if concepts:
        lines.append("# Concepts")
        lines.append("")
        for concept in concepts:
            filename = (concept.id or "concepts/untitled").split("/")[-1]
            title = concept.title or filename
            suffix = f" - {concept.description}" if concept.description else ""
            lines.append(f"* [{title}]({filename}{_CONCEPT_SUFFIX}){suffix}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def _directory_description(concepts: list[OkfConcept]) -> str | None:
    for concept in concepts:
        if concept.description:
            return concept.description
    return None
