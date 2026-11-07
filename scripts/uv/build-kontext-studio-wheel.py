#!/usr/bin/env python3
"""
Build script for kontext-studio unified single-wheel distribution.

Bundles all `kontext.*` namespace packages (from py/kontext-*) and static
frontend app assets into a single wheel archive ready for PyPI or pip
installation.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT_DIR / "dist" / "python"


def parse_requirement(req_str: str) -> tuple[str, str, str]:
    """Parse a requirement string into (lowercase_name, extras_str, specifier_str).

    Handles both PEP 508 style (``requests>=2.0``) and the uv-style
    parenthesized form used by generated manifests (``requests (>=2.0)``).
    """
    req_str = req_str.strip()
    # Normalize the uv-style parenthesized specifier: "name (>=1,<2)" -> "name >=1,<2"
    m = re.match(r"^([a-zA-Z0-9_\-\.]+)(?:\[(.*?)\])?\s*\((.*)\)$", req_str)
    if m:
        name, extras, spec = m.groups()
        return name.lower(), extras or "", f" {spec.strip()}" if spec.strip() else ""

    m = re.match(r"^([a-zA-Z0-9_\-\.]+)(?:\[(.*?)\])?(.*)$", req_str)
    if not m:
        return req_str.lower(), "", ""
    name, extras, spec = m.groups()
    return name.lower(), extras or "", spec or ""


def aggregate_external_dependencies(py_dir: Path) -> list[str]:
    """
    Collect and deduplicate external dependencies across all py/*/pyproject.toml files.
    Excludes workspace internal `kontext-*` packages.
    """
    internal_packages = set()

    for pyproject in py_dir.glob("*/pyproject.toml"):
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
            p_name = data.get("project", {}).get("name")
            if p_name:
                internal_packages.add(p_name)

    raw_deps: list[str] = []
    for pyproject in py_dir.glob("*/pyproject.toml"):
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
            for d in data.get("project", {}).get("dependencies", []):
                if not any(d.startswith(i) for i in internal_packages):
                    raw_deps.append(d)

    req_map: dict[str, dict] = {}
    for r in raw_deps:
        norm_name, extras, spec = parse_requirement(r)
        key = norm_name
        if key not in req_map:
            # Derive the display name (with original casing) from the raw requirement.
            head = re.split(r"\s*[([]|[<>=!~;\s]", r.strip(), maxsplit=1)[0].strip()
            req_map[key] = {
                "orig_name": head or norm_name,
                "extras": set(),
                "specs": set(),
            }
        if extras:
            for ex in extras.split(","):
                req_map[key]["extras"].add(ex.strip())
        if spec:
            # Keep only well-formed specifier clauses (drop stray parens).
            for clause in spec.strip().strip("()").split(","):
                clause = clause.strip()
                if re.match(r"^[<>=!~]", clause):
                    req_map[key]["specs"].add(clause)

    final_deps: list[str] = []
    for info in sorted(req_map.values(), key=lambda entry: entry["orig_name"].lower()):
        name = info["orig_name"]
        extras_str = f"[{','.join(sorted(info['extras']))}]" if info["extras"] else ""
        specs = sorted(info["specs"], reverse=True)
        spec_str = specs[0] if specs else ""
        final_deps.append(f"{name}{extras_str}{spec_str}".strip())

    return final_deps


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
    args = parser.parse_args()

    out_dir = args.out_dir.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.build_app:
        print("🔨 Building frontend app with pnpm...")
        subprocess.run(["pnpm", "--filter", "@kontext-labs/app", "build"], cwd=ROOT_DIR, check=True)

    # Sync app assets to the labs package
    sync_script = ROOT_DIR / "scripts" / "sync-app-assets.sh"
    if sync_script.is_file():
        print("🔄 Running asset sync script...")
        subprocess.run(["bash", str(sync_script)], cwd=ROOT_DIR, check=True)

    py_dir = ROOT_DIR / "py"
    labs_pyproject_path = py_dir / "kontext-labs" / "pyproject.toml"

    if not labs_pyproject_path.is_file():
        print(f"❌ Error: {labs_pyproject_path} not found.", file=sys.stderr)
        sys.exit(1)

    with open(labs_pyproject_path, "rb") as f:
        labs_toml = tomllib.load(f)

    # Aggregate all external dependencies
    aggregated_deps = aggregate_external_dependencies(py_dir)

    staging_dir = Path(tempfile.mkdtemp(prefix="kontext_studio_build_"))
    try:
        print(f"🏗️  Staging unified kontext-studio package in {staging_dir}...")
        staged_src_kontext = staging_dir / "src" / "kontext"
        staged_src_kontext.mkdir(parents=True, exist_ok=True)

        # 1. Copy all namespace packages
        copy_namespace_packages(py_dir, staged_src_kontext)

        # 2. Copy README.md and the license/notice files the wheel distributes.
        labs_readme = py_dir / "kontext-labs" / "README.md"
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
