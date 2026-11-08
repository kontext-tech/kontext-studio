#!/usr/bin/env python3
"""Assemble the bundled Python runtime for the desktop app.

Produces `desktop/src-tauri/resources/`:

    python/      python-build-standalone + the desktop wheel and deps
    wheelhouse/  offline wheels for the kernel venv
    build-info.json

The app wheel is built with the `desktop` dependency profile, which drops the
warehouse drivers that need system libraries. Pass `--wheel` to reuse a wheel
built elsewhere, or `--skip-app-build` to reuse the current `app/dist`.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tarfile
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DESKTOP_DIR = REPO_ROOT / "desktop"
LOCK_FILE = DESKTOP_DIR / "runtime.lock.json"
KERNEL_REQUIREMENTS = DESKTOP_DIR / "requirements" / "kernel.txt"
DEFAULT_OUT = DESKTOP_DIR / "src-tauri" / "resources"
WHEEL_DIR = REPO_ROOT / "dist" / "desktop"
CACHE_DIR = DESKTOP_DIR / ".cache" / "python-build-standalone"

_SMOKE_IMPORTS = (
    "import kontext.labs, kontext.api, kontext.runtime;"
    "import duckdb, pyarrow, pyiceberg, lancedb, fastembed, tantivy;"
    "print('kontext runtime ok')"
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: list[str], *, env: dict[str, str] | None = None) -> None:
    print("$ " + " ".join(command))
    subprocess.run(command, check=True, env=env)


def _default_arch() -> str:
    if sys.platform == "win32":
        return "win-x64"
    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        return "arm64"
    if machine in {"x86_64", "amd64"}:
        return "x64"
    raise SystemExit(f"Unsupported host architecture: {machine}")


def _runtime_python(python_dir: Path, arch: dict) -> Path:
    if arch["platform"] == "windows":
        return python_dir / "python.exe"
    return python_dir / "bin" / "python3"


def _site_packages(python_dir: Path, arch: dict, python_version: str) -> Path:
    if arch["platform"] == "windows":
        return python_dir / "Lib" / "site-packages"
    major_minor = ".".join(python_version.split(".")[:2])
    return python_dir / "lib" / f"python{major_minor}" / "site-packages"


def _download_pbs(arch: dict) -> Path:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    archive = CACHE_DIR / Path(arch["url"]).name
    if not archive.is_file() or _sha256(archive) != arch["sha256"]:
        print(f"Downloading {arch['url']}")
        with urllib.request.urlopen(arch["url"], timeout=120) as response:
            archive.write_bytes(response.read())
    actual = _sha256(archive)
    if actual != arch["sha256"]:
        raise SystemExit(
            f"python-build-standalone checksum mismatch for {archive.name}: "
            f"expected {arch['sha256']}, got {actual}"
        )
    return archive


def _extract_pbs(archive: Path, out_dir: Path) -> Path:
    python_dir = out_dir / "python"
    shutil.rmtree(python_dir, ignore_errors=True)
    print(f"Extracting {archive.name}")
    with tarfile.open(archive, "r:gz") as tar:
        tar.extractall(out_dir, filter="data")
    if not python_dir.is_dir():
        raise SystemExit(f"Archive did not contain a top-level python/ directory: {archive}")
    return python_dir


def _find_wheel(explicit: str | None) -> Path:
    if explicit:
        wheel = Path(explicit).resolve()
        if not wheel.is_file():
            raise SystemExit(f"Wheel not found: {wheel}")
        return wheel
    wheels = sorted(
        WHEEL_DIR.glob("kontext_studio-*.whl"),
        key=lambda path: path.stat().st_mtime,
    )
    if not wheels:
        raise SystemExit(f"No desktop wheel in {WHEEL_DIR}. Run without --wheel to build one.")
    return wheels[-1]


def _build_wheel(build_app: bool) -> Path:
    WHEEL_DIR.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "uv" / "build-kontext-studio-wheel.py"),
        "--profile",
        "desktop",
        "--out-dir",
        str(WHEEL_DIR),
    ]
    if build_app:
        command.append("--build-app")
    _run(command)
    return _find_wheel(None)


def _install_wheel(
    python: Path,
    site_packages: Path,
    wheel: Path,
    deployment_target: str,
) -> None:
    env = dict(os.environ)
    if platform.system() == "Darwin":
        env["MACOSX_DEPLOYMENT_TARGET"] = deployment_target

    if shutil.which("uv"):
        command = [
            "uv",
            "pip",
            "install",
            "--python",
            str(python),
            "--target",
            str(site_packages),
            "--only-binary=:all:",
            "--upgrade",
            "--no-cache",
            str(wheel),
        ]
    else:
        command = [
            str(python),
            "-m",
            "pip",
            "install",
            "--target",
            str(site_packages),
            "--only-binary=:all:",
            "--upgrade",
            "--disable-pip-version-check",
            str(wheel),
        ]
    _run(command, env=env)


def _platform_tag(arch: dict, deployment_target: str) -> str:
    if arch["platform"] == "windows":
        return "win_amd64"
    machine = "arm64" if arch["target"].startswith("aarch64") else "x86_64"
    return f"macosx_{deployment_target.replace('.', '_')}_{machine}"


def _build_kernel_wheelhouse(
    python: Path,
    arch: dict,
    wheelhouse: Path,
    deployment_target: str,
    python_version: str,
) -> None:
    shutil.rmtree(wheelhouse, ignore_errors=True)
    wheelhouse.mkdir(parents=True, exist_ok=True)
    abi = "cp" + python_version.replace(".", "")[:3]
    _run(
        [
            str(python),
            "-m",
            "pip",
            "download",
            "--only-binary=:all:",
            "--platform",
            _platform_tag(arch, deployment_target),
            "--python-version",
            ".".join(python_version.split(".")[:2]),
            "--implementation",
            "cp",
            "--abi",
            abi,
            "--dest",
            str(wheelhouse),
            "--requirement",
            str(KERNEL_REQUIREMENTS),
            "--disable-pip-version-check",
            "--progress-bar",
            "off",
        ]
    )


def _copy_notices(out_dir: Path) -> None:
    target = out_dir / "third-party"
    target.mkdir(parents=True, exist_ok=True)
    for name in ("THIRD_PARTY_NOTICES.md", "LICENSE"):
        source = REPO_ROOT / name
        if source.is_file():
            shutil.copy2(source, target / name)


def _prune_and_compile(python: Path, site_packages: Path) -> None:
    for cache in site_packages.rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    _run([str(python), "-m", "compileall", "-q", str(site_packages)])


def _installed_packages(python: Path) -> list[dict]:
    result = subprocess.run(
        [
            str(python),
            "-m",
            "pip",
            "list",
            "--format=json",
            "--disable-pip-version-check",
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return []
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    return payload if isinstance(payload, list) else []


def _dir_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--arch",
        choices=("arm64", "x64", "win-x64"),
        default=None,
        help="Target architecture (default: the host architecture).",
    )
    parser.add_argument("--wheel", default=None, help="Use an existing desktop wheel.")
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"Resource directory (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--skip-wheelhouse",
        action="store_true",
        help="Reuse an existing kernel wheelhouse instead of downloading it.",
    )
    parser.add_argument(
        "--skip-app-build",
        action="store_true",
        help="Reuse app/dist instead of rebuilding the frontend.",
    )
    parser.add_argument(
        "--skip-smoke",
        action="store_true",
        help="Skip the import smoke test.",
    )
    args = parser.parse_args()

    lock = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
    arch_name = args.arch or _default_arch()
    arch = lock["architectures"][arch_name]
    python_version = lock["pythonVersion"]
    deployment_target = lock.get("deploymentTarget", "13.0")
    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    archive = _download_pbs(arch)
    python_dir = _extract_pbs(archive, out_dir)
    python = _runtime_python(python_dir, arch)
    site_packages = _site_packages(python_dir, arch, python_version)
    if not python.is_file():
        raise SystemExit(f"Bundled interpreter is missing: {python}")
    if not site_packages.is_dir():
        raise SystemExit(f"Bundled site-packages directory is missing: {site_packages}")

    wheel = _find_wheel(args.wheel) if args.wheel else _build_wheel(not args.skip_app_build)
    print(f"Installing {wheel.name} into {site_packages}")
    _install_wheel(python, site_packages, wheel, deployment_target)

    wheelhouse = out_dir / "wheelhouse"
    if args.skip_wheelhouse:
        if not wheelhouse.is_dir():
            raise SystemExit(f"--skip-wheelhouse was passed but {wheelhouse} is missing")
    else:
        _build_kernel_wheelhouse(
            python,
            arch,
            wheelhouse,
            deployment_target,
            python_version,
        )

    _prune_and_compile(python, site_packages)
    _copy_notices(out_dir)

    if not args.skip_smoke:
        _run([str(python), "-E", "-s", "-c", _SMOKE_IMPORTS])

    info = {
        "schema": 1,
        "builtAt": datetime.now(UTC).isoformat(),
        "arch": arch_name,
        "target": arch["target"],
        "pythonVersion": python_version,
        "pbsRelease": lock["release"],
        "deploymentTarget": deployment_target,
        "wheel": wheel.name,
        "wheelSha256": _sha256(wheel),
        "runtimeBytes": _dir_size(python_dir),
        "wheelhouseBytes": _dir_size(wheelhouse),
        "packages": _installed_packages(python),
    }
    (out_dir / "build-info.json").write_text(
        json.dumps(info, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "Assembled "
        f"{arch_name}: runtime={info['runtimeBytes'] / (1024 * 1024):.1f} MiB, "
        f"wheelhouse={info['wheelhouseBytes'] / (1024 * 1024):.1f} MiB"
    )


if __name__ == "__main__":
    main()
