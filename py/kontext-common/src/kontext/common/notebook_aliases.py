"""Notebook-scoped SQL block aliases (shared layer).

A SQL block's result table is addressable inside its notebook by a stable
alias (``df_1``, ``sales_summary``, ...) instead of its UUID. Python blocks
load it with ``await kontext.load_data(alias)``; resolution happens at block
execution from the persisted document (Jupyter-style binding: a name only
becomes loadable once the block has run and saved results).

Lives in the common layer because both the notebook editor (binding on save)
and the execution service (binding at python-run time, resolution) need it;
it imports only ``kontext.schema``.
"""

from __future__ import annotations

import logging
import re

from kontext.schema import NotebookDocument, SqlBlock

logger = logging.getLogger(__name__)

# Kept in sync with the pattern on SqlBlockData in the ts/schema contract
# (zod `.regex` on the `alias` field). Pydantic enforces it on every parse,
# so validation here is a belt-and-braces guard for alias *edits*.
ALIAS_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]{0,63}$"

_NUMBERS_IN_AUTO_ALIAS = re.compile(r"^df_(\d+)$")


def _sql_block_roots(notebook: NotebookDocument) -> list[SqlBlock]:
    roots: list[SqlBlock] = []
    for block in notebook.blocks:
        root = block.root
        if isinstance(root, SqlBlock):
            roots.append(root)
    return roots


def collect_existing_aliases(notebook: NotebookDocument) -> set[str]:
    """Return every alias currently declared in the notebook."""
    return {str(root.data.alias) for root in _sql_block_roots(notebook) if root.data.alias}


def next_auto_alias(notebook: NotebookDocument) -> str:
    """Next free auto alias: max numbered ``df_N`` plus one (monotonic).

    Deleted/reordered blocks never renumber survivors, so downstream code
    referencing ``df_1`` keeps pointing at the same table.
    """
    highest = max(
        (
            int(match.group(1))
            for root in _sql_block_roots(notebook)
            if root.data.alias and (match := _NUMBERS_IN_AUTO_ALIAS.match(root.data.alias))
        ),
        default=0,
    )
    return f"df_{highest + 1}"


def normalize_sql_aliases(notebook: NotebookDocument) -> list[str]:
    """Normalize aliases on a notebook document, mutating it in place.

    - SQL blocks that persisted results (have a ``data_ref``) but carry no
      alias receive one: ``df_N`` with ``N`` monotonic per notebook.
    - Declared aliases must be unique within the notebook.

    Returns the aliases assigned by this call (empty when none). Raises
    ``ValueError`` with an actionable message on invalid or duplicate
    user-renamed aliases.
    """
    assigned: list[str] = []
    blocks = _sql_block_roots(notebook)

    seen: dict[str, str] = {}
    for root in blocks:
        if not root.data.alias:
            continue
        block_id = str(root.id)
        previous = seen.get(root.data.alias)
        if previous is not None:
            raise ValueError(
                f"Duplicate SQL block alias '{root.data.alias}' is used by both "
                f"block {previous} and block {block_id}; aliases must be unique "
                "within a notebook."
            )
        seen[root.data.alias] = block_id

    for root in blocks:
        if root.data.alias or not root.data.data_ref or not root.data.data_ref.data_id:
            continue
        root.data.alias = next_auto_alias(notebook)
        assigned.append(str(root.data.alias))
        logger.debug(
            "Assigned SQL block alias %s to block %s%s",
            root.data.alias,
            root.id,
            f" (table {root.data.data_ref.data_id})",
        )
    return assigned
