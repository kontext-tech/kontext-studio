"""Published dependency metadata must match real source imports.

The Python *source* import graph is enforced by ``test_architecture_boundaries``,
but the *published* graph drifted silently for a long time: distributions
declared dependencies they never imported (``engine -> query``,
``execution -> runtime``) and imported dependencies they never declared
(``catalog -> jobs``). Wheels built outside the uv workspace failed to install
or import.

This test derives the real per-package import roots from ``src/kontext/<root>``
and compares them against the declared ``kontext-*`` dependencies.

Rules:

- Every package imported from a package's source must be declared.
- Extra declared dependencies are allowed only for the composition roots
  (``kontext-api`` and ``kontext-labs``), which intentionally pin the full
  runtime graph for deployment.
- ``ALLOWED_IMPLICIT`` lists the *known* violations that are intentionally
  retained. Add a package there only with an inline justification.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

#: Import roots that exist in source but are not (yet) declared dependencies.
#: Each entry must reference the plan item that will remove it.
ALLOWED_IMPLICIT: dict[str, set[str]] = {}

#: Packages that may declare dependencies they do not import directly
#: (composition roots pinning a deployable graph). Per AGENTS.md,
#: ``kontext-runtime`` and ``kontext-labs`` are the composition roots;
#: ``kontext-api`` is the hosted entrypoint with the same role.
COMPOSITION_ROOTS = {"kontext-api", "kontext-labs", "kontext-runtime"}

_IMPORT_ROOT_RE = re.compile(r"^\s*(?:from|import)\s+kontext\.([a-z_][a-z0-9_]*)", re.MULTILINE)


def _workspace_packages() -> dict[str, Path]:
    members = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text())["tool"]["uv"]["workspace"][
        "members"
    ]
    return {Path(member).name: REPO_ROOT / member for member in members}


def _import_roots(package_dir: Path) -> set[str]:
    """First-path segments imported under ``kontext.*`` from package source."""
    roots: set[str] = set()
    for source in sorted((package_dir / "src").rglob("*.py")):
        text = source.read_text(errors="ignore")
        roots.update(_IMPORT_ROOT_RE.findall(text))
    return roots


def _own_root(package_dir: Path) -> str | None:
    """The importable root directory (``src/kontext/<root>``) of a package."""
    kontext_dir = package_dir / "src" / "kontext"
    if not kontext_dir.is_dir():
        return None
    roots = [
        child.name
        for child in sorted(kontext_dir.iterdir())
        if child.is_dir() and not child.name.startswith("_")
    ]
    return roots[0] if roots else None


def _declared_roots(
    packages: dict[str, Path],
) -> tuple[dict[str, set[str]], list[str]]:
    """Map every package to the import roots of its declared kontext deps."""
    dist_to_root = {
        dist: root for dist, pdir in packages.items() if (root := _own_root(pdir)) is not None
    }
    declared: dict[str, set[str]] = {}
    unknown: list[str] = []
    for dist_name, package_dir in packages.items():
        manifest = tomllib.loads((package_dir / "pyproject.toml").read_text())
        roots = set()
        for dep in manifest["project"].get("dependencies", []):
            base = dep.split("[")[0].strip()
            if not base.startswith("kontext-"):
                continue
            if base in dist_to_root:
                roots.add(dist_to_root[base])
            else:
                unknown.append(f"{dist_name}: declares unknown workspace dep {base!r}")
        declared[dist_name] = roots
    return declared, unknown


def test_declared_dependencies_match_source_imports() -> None:
    packages = _workspace_packages()
    declared, unknown = _declared_roots(packages)

    problems: list[str] = [*unknown]

    for dist_name in sorted(packages):
        package_dir = packages[dist_name]
        imported = _import_roots(package_dir)
        own_root = _own_root(package_dir)
        imported_roots = imported - ({own_root} if own_root else set())
        declared_roots = declared[dist_name]

        unexpected = imported_roots - declared_roots
        unexpected -= ALLOWED_IMPLICIT.get(dist_name, set())
        if unexpected:
            problems.append(f"{dist_name}: imports {sorted(unexpected)} without declaring them")

        extras = declared_roots - imported_roots
        if extras and dist_name not in COMPOSITION_ROOTS:
            problems.append(
                f"{dist_name}: declares {sorted(extras)} but never imports them; "
                f"only composition roots may pin the deployable graph"
            )

    assert not problems, "\n".join(problems)


def test_allowlisted_violations_are_exhaustive() -> None:
    """Keep the known-implicit list honest: entries must still be violated."""
    packages = _workspace_packages()
    declared, _ = _declared_roots(packages)

    stale: list[str] = []
    for dist_name, allowed in ALLOWED_IMPLICIT.items():
        still_missing = _import_roots(packages[dist_name]) - declared[dist_name]
        for root in allowed - still_missing:
            stale.append(f"{dist_name}: {root} is now declared; drop the entry")

    assert not stale, "\n".join(stale)
