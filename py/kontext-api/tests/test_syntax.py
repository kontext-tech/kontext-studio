"""
Test that all Python modules can be imported without syntax errors.

This test acts as an early warning system during refactoring to catch
basic syntax errors and import issues before running more complex tests.
"""

import importlib
from pathlib import Path

import pytest


def find_python_modules(package_path: Path, package_name: str) -> list[str]:
    """
    Recursively find all Python modules in a package.

    Args:
        package_path: Path to the package directory
        package_name: Fully qualified package name

    Returns:
        List of module names that can be imported
    """
    modules = []

    # Add the package itself if it has __init__.py
    if (package_path / "__init__.py").exists():
        modules.append(package_name)

    # Find all Python files and subdirectories
    for item in package_path.iterdir():
        if item.name.startswith("_") and item.name != "__init__.py":
            continue  # Skip private modules

        if item.is_file() and item.suffix == ".py":
            # Add the module (remove .py extension)
            module_name = f"{package_name}.{item.stem}"
            modules.append(module_name)

        elif item.is_dir() and (item / "__init__.py").exists():
            # Recursively process subpackages
            subpackage_name = f"{package_name}.{item.name}"
            modules.extend(find_python_modules(item, subpackage_name))

    return modules


# Find the kontext.api package
api_package_path = Path(__file__).parent.parent / "src" / "kontext" / "api"
api_modules = find_python_modules(api_package_path, "kontext.api")


@pytest.mark.parametrize("module_name", api_modules)
def test_module_imports(module_name: str):
    """
    Test that each module can be imported without errors.

    This catches:
    - Syntax errors
    - Missing imports
    - Import cycle issues
    - Module-level execution errors
    """
    try:
        importlib.import_module(module_name)
    except Exception as e:
        pytest.fail(f"Failed to import {module_name}: {type(e).__name__}: {e}", pytrace=True)


def test_all_routers_importable():
    """
    Specific test for all router modules since they're critical for the API.

    This provides a quick summary of router health without waiting for
    individual parametrized tests.
    """
    routers_path = api_package_path / "routers"
    router_modules = [
        f"kontext.api.routers.{p.stem}"
        for p in routers_path.glob("*.py")
        if not p.name.startswith("_")
    ]

    failed_routers = []
    for router_module in router_modules:
        try:
            importlib.import_module(router_module)
        except Exception as e:
            failed_routers.append(f"{router_module}: {type(e).__name__}: {e}")

    if failed_routers:
        pytest.fail(
            f"Failed to import {len(failed_routers)} router(s):\n"
            + "\n".join(f"  - {r}" for r in failed_routers)
        )
