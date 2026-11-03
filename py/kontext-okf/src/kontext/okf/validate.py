"""OKF bundle conformance validation (OKF v0.2 §11).

A bundle is conformant when:

1. Every non-reserved ``.md`` file contains a parseable YAML frontmatter block.
2. Every frontmatter block contains a non-empty ``type`` field.
3. Every reserved file (``index.md``, ``log.md``) follows the structure in §8
   and §9 respectively when present.

This is a report, not a gate: the spec is deliberately permissive, so callers
decide whether to reject an import or merely surface warnings. ``validate_bundle``
collects *all* issues rather than failing on the first.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .frontmatter import concept_from_frontmatter

#: File suffix for OKF concept files.
_CONCEPT_SUFFIX = ".md"

#: Reserved filenames with defined structure (OKF §3.1).
_RESERVED_FILENAMES = frozenset({"index.md", "log.md"})

#: ``log.md`` date headings MUST use ISO 8601 ``YYYY-MM-DD`` (OKF §9).
_LOG_DATE_HEADING = re.compile(r"^##\s+(\d{4}-\d{2}-\d{2})\s*$")

#: Frontmatter delimiter (OKF §4).
_DELIMITER = "---"


@dataclass(frozen=True)
class ConformanceIssue:
    """A single conformance problem, tagged with the rule it violates."""

    rule: int
    path: str
    message: str


@dataclass
class BundleConformance:
    """The result of validating a bundle against OKF §11."""

    issues: list[ConformanceIssue] = field(default_factory=list)
    concept_count: int = 0

    @property
    def conformant(self) -> bool:
        return not self.issues


def validate_bundle(bundle_dir: str | Path) -> BundleConformance:
    """Validate an OKF bundle directory against the three conformance rules."""
    root = Path(bundle_dir)
    result = BundleConformance()

    if not root.is_dir():
        result.issues.append(ConformanceIssue(0, str(root), "Bundle directory not found"))
        return result

    for path in sorted(root.rglob(f"*{_CONCEPT_SUFFIX}")):
        relative = path.relative_to(root).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            result.issues.append(ConformanceIssue(1, relative, f"Unreadable: {exc}"))
            continue

        if path.name in _RESERVED_FILENAMES:
            _validate_reserved(path, relative, text, is_root=path.parent == root, result=result)
            continue

        result.concept_count += 1
        try:
            concept_from_frontmatter(text)
        except ValueError as exc:
            message = str(exc)
            # Distinguish the missing-`type` case (rule 2) from a general
            # frontmatter parse failure (rule 1).
            rule = 2 if "required 'type' field" in message else 1
            result.issues.append(ConformanceIssue(rule, relative, message))

    return result


def _validate_reserved(
    path: Path,
    relative: str,
    text: str,
    *,
    is_root: bool,
    result: BundleConformance,
) -> None:
    if path.name == "index.md":
        _validate_index(relative, text, is_root=is_root, result=result)
    elif path.name == "log.md":
        _validate_log(relative, text, result=result)


def _split_leading_frontmatter(text: str) -> tuple[str | None, str]:
    """Return ``(frontmatter, body)``; ``frontmatter`` is ``None`` if absent."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != _DELIMITER:
        return None, text
    for index in range(1, len(lines)):
        if lines[index].strip() == _DELIMITER:
            return "\n".join(lines[1:index]), "\n".join(lines[index + 1 :])
    # Unterminated block: treat the whole thing as body-less invalid frontmatter.
    return "\n".join(lines[1:]), ""


def _validate_index(relative: str, text: str, *, is_root: bool, result: BundleConformance) -> None:
    """OKF §8: index files carry no frontmatter, except root ``okf_version``."""
    frontmatter, _body = _split_leading_frontmatter(text)

    if frontmatter is not None:
        if not is_root:
            result.issues.append(
                ConformanceIssue(
                    3,
                    relative,
                    "Only a bundle-root index.md may carry frontmatter (§8)",
                )
            )
        else:
            import yaml

            try:
                data = yaml.safe_load(frontmatter) or {}
            except yaml.YAMLError as exc:
                result.issues.append(
                    ConformanceIssue(3, relative, f"Unparseable index frontmatter: {exc}")
                )
                return
            if not isinstance(data, dict) or set(data) - {"okf_version"}:
                result.issues.append(
                    ConformanceIssue(
                        3,
                        relative,
                        "Root index.md frontmatter may only contain 'okf_version' (§8, §12)",
                    )
                )

    # Body grouping under headings is a SHOULD (§8), not a hard rule, so it is
    # not reported as a conformance issue.


def _validate_log(relative: str, text: str, *, result: BundleConformance) -> None:
    """OKF §9: log date headings MUST be ISO 8601 ``YYYY-MM-DD``."""
    _, body = _split_leading_frontmatter(text)
    for line in body.splitlines():
        if line.startswith("## ") and not _LOG_DATE_HEADING.match(line):
            result.issues.append(
                ConformanceIssue(
                    3,
                    relative,
                    f"log.md heading must be '## YYYY-MM-DD': {line.strip()!r}",
                )
            )
