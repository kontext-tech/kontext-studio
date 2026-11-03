import ast
from pathlib import Path

ROUTERS_DIR = Path(__file__).resolve().parents[1] / "src" / "kontext" / "api" / "routers"
TARGET_ROUTERS = [
    "auth.py",
    "catalog.py",
    "chats.py",
    "events.py",
    "files.py",
    "jobs.py",
    "job_runs.py",
    "project.py",
    "projects.py",
    "query.py",
    "query_sessions.py",
    "runs.py",
]


def test_refactored_routers_do_not_import_persistence_directly():
    violations: list[str] = []

    for router_name in TARGET_ROUTERS:
        router_path = ROUTERS_DIR / router_name
        module = ast.parse(router_path.read_text(encoding="utf-8"))

        for node in ast.walk(module):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module == "kontext.data" or node.module.startswith("kontext.data."):
                    violations.append(f"{router_name}: from {node.module} import ...")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "kontext.data" or alias.name.startswith("kontext.data."):
                        violations.append(f"{router_name}: import {alias.name}")

    assert not violations, "Routers should depend on API services, not kontext.data:\n" + "\n".join(
        violations
    )
