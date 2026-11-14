#!/usr/bin/env python3
"""
Build script for kontext-studio unified single-wheel distribution.

Bundles all `kontext.*` namespace packages (from py/kontext-*) and static
frontend app assets into a single wheel archive ready for PyPI or pip
installation.
"""

from __future__ import annotations

import argparse
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT_DIR / "dist" / "python"

# Warehouse drivers are deployment-specific: pyodbc needs a system unixODBC,
# and teradatasql is a large proprietary client. The desktop build keeps the
# code paths (they are lazy/SQLAlchemy dialect strings) but not the drivers.
DESKTOP_EXCLUDED_PACKAGES = frozenset(
    {
        "psycopg",
        "psycopg-binary",
        "pymysql",
        "pyodbc",
        "oracledb",
        "teradatasql",
        "teradatasqlalchemy",
    }
)


def parse_requirement(req_str: str) -> tuple[str, str, str, str]:
    """Parse a requirement into (lowercase_name, extras, specifier, marker).

    Handles both PEP 508 style (``requests>=2.0``) and the uv-style
    parenthesized form used by generated manifests (``requests (>=2.0)``).
    """
    req_str = req_str.strip()
    marker = ""
    if ";" in req_str:
        req_str, _, marker = req_str.partition(";")
        req_str, marker = req_str.strip(), marker.strip()

    m = re.match(r"^([a-zA-Z0-9_\-\.]+)(?:\[(.*?)\])?\s*\((.*)\)$", req_str)
    if m:
        name, extras, spec = m.groups()
        return name.lower(), extras or "", spec.strip(), marker

    m = re.match(r"^([a-zA-Z0-9_\-\.]+)(?:\[(.*?)\])?(.*)$", req_str)
    if not m:
        return req_str.lower(), "", "", marker
    name, extras, spec = m.groups()
    return name.lower(), extras or "", spec.strip(), marker


def _display_name(raw: str) -> str:
    """Keep the author's casing for a package name; pip normalizes it anyway."""
    head = re.split(r"\s*[([]|[<>=!~;\s]", raw.strip(), maxsplit=1)[0].strip()
    return head


def aggregate_external_dependencies(py_dir: Path) -> list[str]:
    """
    Collect and deduplicate external dependencies across all py/*/pyproject.toml files.

    Workspace `kontext-*` packages are vendored into the wheel instead of being
    installed, so their dependencies are hoisted here. A workspace dependency
    that requests an extra (`kontext-job[catalog]`) is expanded: otherwise the
    packages and version bounds that extra adds would be missing from the wheel.
    """
    projects: dict[str, dict] = {}
    for pyproject in sorted(py_dir.glob("*/pyproject.toml")):
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        project_name = data.get("project", {}).get("name")
        if project_name:
            projects[project_name] = data["project"]

    requirements: list[str] = []

    def collect(dep: str, seen: frozenset[tuple[str, str]]) -> None:
        norm_name, extras, _, _ = parse_requirement(dep)
        if norm_name not in projects:
            requirements.append(dep)
            return
        for extra in {item.strip() for item in extras.split(",") if item.strip()}:
            if (norm_name, extra) in seen:
                continue
            extra_deps = projects[norm_name].get("optional-dependencies", {}).get(extra, [])
            for extra_dep in extra_deps:
                collect(extra_dep, seen | {(norm_name, extra)})

    for project in projects.values():
        for dep in project.get("dependencies", []):
            collect(dep, frozenset())

    # Merge requirements per (package, marker) pair: extras union, and every
    # specifier clause is kept so no bound is silently dropped when members
    # disagree.
    grouped: dict[tuple[str, str], dict] = {}
    for raw in requirements:
        norm_name, extras, spec, marker = parse_requirement(raw)
        info = grouped.setdefault(
            (norm_name, marker),
            {"orig_name": _display_name(raw) or norm_name, "extras": set(), "specs": set()},
        )
        info["extras"].update(item.strip() for item in extras.split(",") if item.strip())
        for clause in spec.strip().strip("()").split(","):
            clause = clause.strip()
            if re.match(r"^[<>=!~]", clause):
                info["specs"].add(clause)

    final_deps: list[str] = []
    for (_, marker), info in sorted(
        grouped.items(), key=lambda entry: (entry[1]["orig_name"].lower(), entry[0][1])
    ):
        extras_str = f"[{','.join(sorted(info['extras']))}]" if info["extras"] else ""
        spec_str = ",".join(sorted(info["specs"]))
        marker_str = f"; {marker}" if marker else ""
        final_deps.append(f"{info['orig_name']}{extras_str}{spec_str}{marker_str}".strip())

    return final_deps


# `kontext-common` declares a pytest plugin for this repository's own suite.
# Re-exporting it would inject that plugin into every project that happens to
# have kontext-studio installed.
_UNEXPORTED_ENTRY_POINT_GROUPS = {"pytest11"}


def aggregate_entry_points(py_dir: Path) -> dict[str, dict[str, str]]:
    """
    Collect entry points declared across all py/*/pyproject.toml files.

    The unified wheel vendors every workspace package into one distribution, so
    an entry point declared by a member (the agent harness plugin, for example)
    only exists if the staged metadata repeats it.
    """
    groups: dict[str, dict[str, str]] = {}

    for pyproject in sorted(py_dir.glob("*/pyproject.toml")):
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        declared = data.get("project", {}).get("entry-points", {})
        for group, entries in declared.items():
            if group in _UNEXPORTED_ENTRY_POINT_GROUPS:
                continue
            groups.setdefault(group, {}).update(entries)

    return groups


def copy_namespace_packages(py_dir: Path, target_src_kontext: Path) -> None:
    """Copy all py/*/src/kontext/* subpackages into the unified target src/kontext directory."""
    for package_dir in sorted(py_dir.glob("kontext-*")):
        src_kontext = package_dir / "src" / "kontext"
        if not src_kontext.is_dir():
            continue

        for item in src_kontext.iterdir():
            target_item = target_src_kontext / item.name
            if item.is_dir():
                if target_item.exists():
                    # Merge directories if subpackage already exists
                    for sub in item.rglob("*"):
                        rel = sub.relative_to(item)
                        dest = target_item / rel
                        if sub.is_dir():
                            dest.mkdir(parents=True, exist_ok=True)
                        else:
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(sub, dest)
                else:
                    shutil.copytree(item, target_item, symlinks=False)
            else:
                shutil.copy2(item, target_item)


def main() -> None:
    # Windows consoles default to a legacy code page (cp1252) that cannot
    # encode the emoji in this script's log lines.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Build unified kontext-studio wheel distribution")
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=OUTPUT_DIR,
        help="Directory to save output wheel",
    )
    parser.add_argument(
        "--build-app",
        action="store_true",
        help="Build frontend app with pnpm before packaging",
    )
    parser.add_argument(
        "--version",
        help=(
            "Override the packaged version without editing committed files. "
            "Used for TestPyPI repeat uploads, which reject an existing version."
        ),
    )
    parser.add_argument(
        "--profile",
        choices=("pypi", "desktop"),
        default="pypi",
        help=(
            "Dependency profile. `pypi` keeps every external dependency; "
            "`desktop` drops warehouse drivers that need system libraries."
        ),
    )
    args = parser.parse_args()

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.build_app:
        print("🔨 Building frontend app with pnpm...")
        pnpm = shutil.which("pnpm")
        if not pnpm:
            raise SystemExit("pnpm not found. Install it with corepack enable pnpm.")
        if platform.system() == "Windows":
            subprocess.run(
                ["cmd", "/c", pnpm, "--filter", "@kontext-tech/app", "build"],
                cwd=ROOT_DIR,
                check=True,
            )
        else:
            subprocess.run(
                [pnpm, "--filter", "@kontext-tech/app", "build"], cwd=ROOT_DIR, check=True
            )

    # Sync app assets to the labs package
    sync_script = ROOT_DIR / "scripts" / "sync-app-assets.sh"
    if sync_script.is_file():
        print("🔄 Running asset sync script...")
        # as_posix: Git Bash on Windows cannot parse backslash-separated paths.
        subprocess.run(["bash", sync_script.as_posix()], cwd=ROOT_DIR, check=True)

    py_dir = ROOT_DIR / "py"
    labs_pyproject_path = py_dir / "kontext-studio" / "pyproject.toml"

    if not labs_pyproject_path.is_file():
        print(f"❌ Error: {labs_pyproject_path} not found.", file=sys.stderr)
        sys.exit(1)

    with open(labs_pyproject_path, "rb") as f:
        labs_toml = tomllib.load(f)

    # Aggregate all external dependencies
    aggregated_deps = aggregate_external_dependencies(py_dir)
    if args.profile == "desktop":
        before = len(aggregated_deps)
        aggregated_deps = [
            dep
            for dep in aggregated_deps
            if parse_requirement(dep)[0] not in DESKTOP_EXCLUDED_PACKAGES
        ]
        print(
            f"🪶 Desktop profile: dropped {before - len(aggregated_deps)} "
            "warehouse-driver dependencies."
        )
    # Merge entry points from every member so plugins such as the agent harness
    # stay discoverable in the unified distribution.
    aggregated_entry_points = aggregate_entry_points(py_dir)

    staging_dir = Path(tempfile.mkdtemp(prefix="kontext_studio_build_"))
    try:
        print(f"🏗️  Staging unified kontext-studio package in {staging_dir}...")
        staged_src_kontext = staging_dir / "src" / "kontext"
        staged_src_kontext.mkdir(parents=True, exist_ok=True)

        # 1. Copy all namespace packages
        copy_namespace_packages(py_dir, staged_src_kontext)

        # 2. Copy README.md and the license/notice files the wheel distributes.
        labs_readme = py_dir / "kontext-studio" / "README.md"
        if labs_readme.is_file():
            shutil.copy2(labs_readme, staging_dir / "README.md")
        else:
            (staging_dir / "README.md").write_text("# Kontext\n\nUnified Kontext distribution.\n")

        license_file = ROOT_DIR / "LICENSE"
        if license_file.is_file():
            shutil.copy2(license_file, staging_dir / "LICENSE")
        notices_file = ROOT_DIR / "THIRD_PARTY_NOTICES.md"
        if notices_file.is_file():
            shutil.copy2(notices_file, staging_dir / "THIRD_PARTY_NOTICES.md")

        # 4. Construct staged pyproject.toml
        staged_project = labs_toml["project"].copy()
        staged_project["dependencies"] = aggregated_deps
        if aggregated_entry_points:
            staged_project["entry-points"] = {
                **staged_project.get("entry-points", {}),
                **aggregated_entry_points,
            }
        if args.version:
            staged_project["version"] = args.version

        staged_pyproject = {
            "project": staged_project,
            "build-system": labs_toml.get(
                "build-system",
                {"requires": ["hatchling"], "build-backend": "hatchling.build"},
            ),
            "tool": {"hatch": {"build": {"targets": {"wheel": {"packages": ["src/kontext"]}}}}},
        }

        staged_toml_path = staging_dir / "pyproject.toml"

        # Format staged pyproject.toml cleanly
        def format_toml(data: dict) -> str:
            lines = ["[project]"]
            p = data["project"]
            lines.append(f'name = "{p["name"]}"')
            lines.append(f'version = "{p["version"]}"')
            lines.append(f'description = "{p["description"]}"')
            lines.append(f'requires-python = "{p["requires-python"]}"')
            lines.append(f'readme = "{p["readme"]}"')
            lines.append('license = { text = "MIT" }')

            lines.append("\ndependencies = [")
            for dep in p["dependencies"]:
                lines.append(f'    "{dep}",')
            lines.append("]")

            if "scripts" in p:
                lines.append("\n[project.scripts]")
                for k, v in p["scripts"].items():
                    lines.append(f'{k} = "{v}"')

            if p.get("entry-points"):
                for group, entries in sorted(p["entry-points"].items()):
                    lines.append(f'\n[project.entry-points."{group}"]')
                    for name, value in sorted(entries.items()):
                        lines.append(f'{name} = "{value}"')

            if "optional-dependencies" in p:
                lines.append("\n[project.optional-dependencies]")
                for opt_k, opt_v in p["optional-dependencies"].items():
                    lines.append(f"{opt_k} = [")
                    for item in opt_v:
                        lines.append(f'    "{item}",')
                    lines.append("]")

            lines.append("\n[build-system]")
            lines.append('requires = ["hatchling"]')
            lines.append('build-backend = "hatchling.build"')

            lines.append("\n[tool.hatch.build.targets.wheel]")
            lines.append('packages = ["src/kontext"]')

            return "\n".join(lines) + "\n"

        staged_toml_path.write_text(format_toml(staged_pyproject), encoding="utf-8")

        print("🚀 Building wheel distribution with uv...")
        subprocess.run(
            ["uv", "build", str(staging_dir), "--wheel", "--out-dir", str(out_dir)],
            check=True,
        )

        print(f"✨ Successfully built unified kontext-studio distribution in {out_dir}:")
        for dist_file in sorted(out_dir.glob("kontext_studio*")):
            print(f"  - {dist_file.name}")

    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
