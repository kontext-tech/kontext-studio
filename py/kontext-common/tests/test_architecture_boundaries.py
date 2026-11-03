from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PY_ROOT = REPO_ROOT / "py"
TOP_LEVEL_MODULE_TO_PACKAGE = {
    "account": "kontext-account",
    "agent": "kontext-agent",
    "agentic": "kontext-agentic",
    "api": "kontext-api",
    "auth": "kontext-auth",
    "catalog": "kontext-catalog",
    "chat": "kontext-chat",
    "common": "kontext-common",
    "data": "kontext-data",
    "engine": "kontext-engine",
    "execution": "kontext-execution",
    "file": "kontext-file",
    "jobs": "kontext-job",
    "kernel": "kontext-kernel",
    "labs": "kontext-labs",
    "llm": "kontext-llm",
    "okf": "kontext-okf",
    "project": "kontext-project",
    "query": "kontext-query",
    "runtime": "kontext-runtime",
    "schema": "kontext-schema",
    "storage": "kontext-storage",
}


def _collect_imports(package_name: str) -> set[str]:
    package_root = PY_ROOT / package_name / "src"
    imports: set[str] = set()
    for path in package_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                for prefix, target in TOP_LEVEL_MODULE_TO_PACKAGE.items():
                    dotted = f"kontext.{prefix}"
                    if node.module == dotted or node.module.startswith(f"{dotted}."):
                        imports.add(target)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    for prefix, target in TOP_LEVEL_MODULE_TO_PACKAGE.items():
                        dotted = f"kontext.{prefix}"
                        if alias.name == dotted or alias.name.startswith(f"{dotted}."):
                            imports.add(target)
    imports.discard(package_name)
    return imports


def _files_importing_package(package_name: str, top_level: str) -> set[str]:
    """Return repo-relative paths in *package_name* importing ``kontext.<top_level>``."""
    dotted = f"kontext.{top_level}"
    offenders: set[str] = set()
    for path in (PY_ROOT / package_name / "src").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module
                and (node.module == dotted or node.module.startswith(f"{dotted}."))
            ):
                offenders.add(str(path.relative_to(REPO_ROOT)))
                break
            if isinstance(node, ast.Import) and any(
                alias.name == dotted or alias.name.startswith(f"{dotted}.") for alias in node.names
            ):
                offenders.add(str(path.relative_to(REPO_ROOT)))
                break
    return offenders


# Third-party agent-harness SDKs. The harness abstraction exists so swapping a
# harness (Agno -> Google ADK, ...) is a composition change, not a rewrite. To
# keep that true, exactly one adapter module may import a harness SDK; every
# other package must go through the neutral `kontext-agent` contracts.
HARNESS_SDK_ROOTS = ("agno", "google.adk", "google.genai")
# Directories permitted to import a harness SDK: one per adapter. Everything
# else in the workspace must go through the neutral `kontext-agent` contracts.
_HARNESS_ADAPTER_DIRS = (PY_ROOT / "kontext-harness-agno" / "src" / "kontext" / "harness" / "agno",)


def _in_harness_adapter_dir(path: Path) -> bool:
    return any(
        path == adapter_dir or adapter_dir in path.parents for adapter_dir in _HARNESS_ADAPTER_DIRS
    )


def _imports_harness_sdk(path: Path) -> bool:
    tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    for node in ast.walk(tree):
        names: list[str] = []
        # Only absolute imports address a third-party SDK. Relative imports
        # (`from ..agno.system import ...`) target the in-repo adapter package
        # `kontext.harness.agno`, not the `agno` distribution.
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.append(node.module)
        elif isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        for name in names:
            if any(name == root or name.startswith(f"{root}.") for root in HARNESS_SDK_ROOTS):
                return True
    return False


def _harness_importing_files() -> set[Path]:
    offenders: set[Path] = set()
    for package in sorted(set(TOP_LEVEL_MODULE_TO_PACKAGE.values())):
        package_root = PY_ROOT / package / "src"
        if not package_root.exists():
            continue
        for path in package_root.rglob("*.py"):
            if _in_harness_adapter_dir(path):
                continue
            if _imports_harness_sdk(path):
                offenders.add(path)
    return offenders


def test_data_package_does_not_depend_on_job_package() -> None:
    assert "kontext-job" not in _collect_imports("kontext-data")


def test_job_package_does_not_depend_on_file_package() -> None:
    assert "kontext-file" not in _collect_imports("kontext-job")


def test_common_is_a_leaf_contract_package() -> None:
    """Common is the shared contract leaf: it may only depend on the schema layer.

    This is a whitelist rather than the earlier blacklist so a new higher-layer
    dependency (engine, catalog, storage, ...) fails the boundary instead of
    silently passing.
    """
    imports = _collect_imports("kontext-common")
    unexpected = imports - {"kontext-schema"}
    assert not unexpected, "kontext-common imports outside its leaf layer: " + ", ".join(
        sorted(unexpected)
    )


def test_engine_is_pure_compute_without_query_orchestration() -> None:
    """Engine implements the query-execution port; it must not import query.

    Query orchestration resolves engines through the
    ``QueryRuntimeProviderProtocol`` seam, so the engine can be swapped for a
    remote/cloud engine without query importing a concrete implementation. The
    reverse (engine -> query) import would break that symmetry.
    """
    assert "kontext-query" not in _collect_imports("kontext-engine")


def test_query_does_not_depend_on_concrete_engine() -> None:
    """Query orchestrates through ports, never a concrete engine package."""
    assert "kontext-engine" not in _collect_imports("kontext-query")


def test_execution_does_not_depend_on_query_or_engine() -> None:
    assert "kontext-query" not in _collect_imports("kontext-execution")
    assert "kontext-engine" not in _collect_imports("kontext-execution")


def _cyclic_edges() -> set[tuple[str, str]]:
    graph = {
        pkg: _collect_imports(pkg) for pkg in sorted(set(TOP_LEVEL_MODULE_TO_PACKAGE.values()))
    }

    def _reachable(start: str, target: str, seen: set[str]) -> bool:
        for dep in graph.get(start, set()):
            if dep == target:
                return True
            if dep not in seen:
                seen.add(dep)
                if _reachable(dep, target, seen):
                    return True
        return False

    edges: set[tuple[str, str]] = set()
    for pkg, deps in graph.items():
        for dep in deps:
            if pkg in graph.get(dep, set()) or _reachable(dep, pkg, {dep}):
                edges.add((pkg, dep))
    return edges


def test_package_import_graph_is_acyclic() -> None:
    """No package may depend (directly or transitively) on a package that depends on it.

    Cycles make the layering ambiguous and force lazy/inline imports to dodge
    them. The workspace graph is fully acyclic; keep it that way.
    """
    cycles = _cyclic_edges()
    assert not cycles, "Cyclic package dependencies: " + ", ".join(
        f"{a} -> {b}" for a, b in sorted(cycles)
    )


def test_llm_does_not_depend_on_deployment_layers() -> None:
    """Model resolution is port-driven; llm must not import these layers."""
    llm_imports = _collect_imports("kontext-llm")
    assert "kontext-runtime" not in llm_imports
    assert "kontext-account" not in llm_imports


def test_agent_imports_stay_within_its_contract_layer() -> None:
    """`kontext-agent` is the shared contract leaf for the agent stack.

    `kontext-chat` and `kontext-data` import it, and harness adapters depend on
    it *instead of* the application layer. It may therefore only depend on the
    shared leaves; the resolved model binding lives in `kontext-common`, so the
    contract layer never imports the model-resolution service.
    """
    imports = _collect_imports("kontext-agent")
    unexpected = imports - {"kontext-common", "kontext-schema"}
    assert not unexpected, "kontext-agent imports outside its contract layer: " + ", ".join(
        sorted(unexpected)
    )


def test_harness_adapters_do_not_import_the_application_or_storage_layers() -> None:
    """A harness distribution is a plugin, not an application dependency.

    Adapters receive the run-state store through `AgentCreationContext`; they
    must not reach into `kontext-agentic` (blueprints/domain tools) or
    `kontext-data` (the platform storage implementation).
    """
    offenders = _files_importing_package(
        "kontext-harness-agno", "agentic"
    ) | _files_importing_package("kontext-harness-agno", "data")
    assert not offenders, "Harness adapter imports the application/storage layer: " + ", ".join(
        sorted(offenders)
    )


def test_kontext_agentic_does_not_depend_on_the_composition_layer() -> None:
    """The neutral AI layer must not import the runtime composition layer.

    Deployment-profile composition (e.g. the local provider built from raw
    headers in ``kontext.api.services.runtime``) belongs to the composition
    roots. ``kontext-agentic`` consumes providers only through the neutral
    provider protocols.
    """
    assert "kontext-runtime" not in _collect_imports("kontext-agentic")


def test_okf_does_not_depend_on_catalog() -> None:
    """OKF projects into a neutral knowledge contract, not the catalog package."""
    assert "kontext-catalog" not in _collect_imports("kontext-okf")


def test_kernel_only_depends_on_common() -> None:
    """The kernel may depend only on the shared contract layer.

    It provides execution topology (harness, manager, runner) plus the
    dependency-free contracts re-exported from ``kontext-common``. Backend
    selection, which needs the managed interpreter, stays in ``kontext-runtime``.
    """
    assert _collect_imports("kontext-kernel") <= {"kontext-common"}


def test_runtime_is_the_only_composition_that_may_wire_engine_and_kernel() -> None:
    """Only the composition layer imports both the engine and the kernel."""
    runtime_imports = _collect_imports("kontext-runtime")
    assert "kontext-engine" in runtime_imports
    assert "kontext-kernel" in runtime_imports


def test_only_the_composition_layer_imports_the_engine() -> None:
    """No orchestration package may import the compute package directly.

    Engine selection goes through the ``QueryRuntimeProviderProtocol`` seam, so
    swapping the engine stays a composition change. ``kontext-runtime`` wires
    the concrete engine (and ``kontext-labs`` as the local server/CLI
    composition root); everyone else resolves engines through ports.
    """
    offenders = {
        pkg
        for pkg in TOP_LEVEL_MODULE_TO_PACKAGE.values()
        if pkg not in {"kontext-runtime", "kontext-labs", "kontext-engine"}
        and "kontext-engine" in _collect_imports(pkg)
    }
    assert not offenders, "Unexpected engine importers outside the composition layer: " + (
        ", ".join(sorted(offenders))
    )


# Sanctioned kernel seam outside the composition layers. It must only ever
# shrink: route kernel calls through a provider port (``create_python_*``) or
# into ``kontext-runtime`` and delete the entry.
#
# ``runs.py`` is the run orchestrator: its force-kill is deliberately
# process-local (a worker-executed run is cancelled via the persisted status),
# lazily imported to avoid a module-load cycle, and the orchestrator holds no
# runtime provider to route through.
KNOWN_EXTERNAL_KERNEL_OFFENDERS: frozenset[str] = frozenset(
    {
        "py/kontext-execution/src/kontext/execution/runs.py",
    }
)


def test_kernel_imports_stay_confined_to_composition_layers() -> None:
    """Kernel wiring (topology, runners, policy) belongs to composition roots.

    Domain packages should run Python through the runtime/kernel seam, not the
    kernel package, so hosted compositions can swap the topology. The
    allowlist documents the offenders that must migrate to the seam over time.
    """
    offenders: set[str] = set()
    for pkg in sorted(set(TOP_LEVEL_MODULE_TO_PACKAGE.values())):
        if pkg in {"kontext-runtime", "kontext-kernel", "kontext-labs"}:
            continue
        offenders |= _files_importing_package(pkg, "kernel")
    unexpected = offenders - set(KNOWN_EXTERNAL_KERNEL_OFFENDERS)
    assert not unexpected, "Kernel imports leaked outside composition layers: " + ", ".join(
        sorted(unexpected)
    )
    stale = set(KNOWN_EXTERNAL_KERNEL_OFFENDERS) - offenders
    assert not stale, "Stale KNOWN_EXTERNAL_KERNEL_OFFENDERS entries: " + ", ".join(sorted(stale))


# Transitional allowlist for direct query -> catalog imports. It must only
# ever shrink: route the access through a provider port and delete the entry.
KNOWN_QUERY_CATALOG_OFFENDERS: frozenset[str] = frozenset(
    {
        # query_session_service.py imports the concrete LakehouseService to
        # resolve lakehouse table URIs; it should move behind a port.
        "py/kontext-query/src/kontext/query/query_session_service.py",
    }
)


def test_query_depends_on_catalog_only_through_documented_seams() -> None:
    """Query orchestration reaches catalog through ports, not concrete imports."""
    offenders = _files_importing_package("kontext-query", "catalog")
    unexpected = offenders - set(KNOWN_QUERY_CATALOG_OFFENDERS)
    assert not unexpected, "Unexpected kontext-query -> kontext-catalog imports: " + ", ".join(
        sorted(unexpected)
    )
    stale = set(KNOWN_QUERY_CATALOG_OFFENDERS) - offenders
    assert not stale, "Stale KNOWN_QUERY_CATALOG_OFFENDERS entries: " + ", ".join(sorted(stale))


# Transitional allowlist for the agentic package's dependence on the chat
# package. It must only ever shrink: lift the shared streaming contracts into
# kontext-common and move chat-specific helpers behind ports.
KNOWN_AGENTIC_CHAT_OFFENDERS: frozenset[str] = frozenset(
    {
        # Protocols + python execution helpers for chat tools, plus the
        # chat-context assembly/token usage split out of `chat_handler.py`
        # (`chat_handler.py` itself no longer imports `kontext-chat`).
        "py/kontext-agentic/src/kontext/agentic/chat_context.py",
        "py/kontext-agentic/src/kontext/agentic/tools/python_tool.py",
    }
)


def test_agentic_depends_on_chat_only_through_documented_seams() -> None:
    offenders = _files_importing_package("kontext-agentic", "chat")
    unexpected = offenders - set(KNOWN_AGENTIC_CHAT_OFFENDERS)
    assert not unexpected, "Unexpected kontext-agentic -> kontext-chat imports: " + ", ".join(
        sorted(unexpected)
    )
    stale = set(KNOWN_AGENTIC_CHAT_OFFENDERS) - offenders
    assert not stale, "Stale KNOWN_AGENTIC_CHAT_OFFENDERS entries: " + ", ".join(sorted(stale))


# Transitional allowlist for harness-SDK imports that predate the adapter
# boundary. It must only ever shrink: move the import behind the adapter in
# `kontext-harness-agno/src/kontext/harness/agno/` (or the neutral
# `kontext-agent` / `kontext-llm` contracts) and delete the entry. Currently empty.
KNOWN_HARNESS_SDK_OFFENDERS: frozenset[str] = frozenset()


def test_only_the_harness_adapter_imports_a_harness_sdk() -> None:
    """Harness SDKs are confined to the adapter directory.

    This is the invariant that makes the abstraction real: if a domain package,
    the LLM catalog, or an event converter can import `agno`, then switching to
    another harness (e.g. Google ADK) requires editing those packages too.
    """
    offenders = {str(path.relative_to(REPO_ROOT)) for path in _harness_importing_files()}
    unexpected = offenders - set(KNOWN_HARNESS_SDK_OFFENDERS)
    assert not unexpected, (
        "Harness SDK imports leaked outside kontext-harness-agno/src/kontext/harness/agno/: "
        + ", ".join(sorted(unexpected))
    )


def _harness_test_dirs() -> tuple[Path, ...]:
    dirs = []
    for package in sorted(set(TOP_LEVEL_MODULE_TO_PACKAGE.values())):
        test_root = PY_ROOT / package / "tests"
        if test_root.exists():
            dirs.append(test_root)
    return tuple(dirs)


def _harness_importing_test_files() -> set[Path]:
    """Scan neutral-package *test* directories for harness-SDK imports.

    Adapter `tests` directories inside the harness dist are exempt, exactly like
    the adapter `src` directory: adapter behavior tests may pin harness types.
    """
    offenders: set[Path] = set()
    for test_root in _harness_test_dirs():
        if "kontext-harness-agno" in test_root.parts:
            continue
        for path in test_root.rglob("*.py"):
            if _imports_harness_sdk(path):
                offenders.add(path)
    return offenders


# Transitional allowlist for harness-SDK imports in neutral-package tests. It
# must only ever shrink: port the test behind the adapter (or to the neutral
# contracts) and delete the entry. Currently empty.
KNOWN_HARNESS_SDK_TEST_OFFENDERS: frozenset[str] = frozenset()


def test_only_the_harness_adapter_imports_a_harness_sdk_in_tests() -> None:
    """Neutral-package tests must not import harness SDKs either.

    The `src` scan above enforces runtime purity; this scan keeps test-surface
    purity so a harness swap does not have to rewrite neutral test suites.
    """
    offenders = {str(path.relative_to(REPO_ROOT)) for path in _harness_importing_test_files()}
    unexpected = offenders - set(KNOWN_HARNESS_SDK_TEST_OFFENDERS)
    assert not unexpected, "Harness SDK imports leaked into neutral test suites: " + ", ".join(
        sorted(unexpected)
    )


# Directories the job registry scans for @job definitions. These modules are
# discovered and executed inside worker processes, so they are the
# worker-portable code: everything they need must arrive through JobContext /
# provider ports. A direct `kontext.data` import ties a job to the local
# SQLite stack and breaks any hosted (API-backed) worker composition.
JOB_DEFINITION_DIRS = (
    PY_ROOT / "kontext-job" / "src" / "kontext" / "jobs" / "definitions",
    PY_ROOT / "kontext-execution" / "src" / "kontext" / "execution" / "job_definitions",
    PY_ROOT / "kontext-query" / "src" / "kontext" / "query" / "jobs",
    PY_ROOT / "kontext-catalog" / "src" / "kontext" / "catalog" / "jobs",
    PY_ROOT / "kontext-file" / "src" / "kontext" / "file" / "jobs",
    PY_ROOT / "kontext-project" / "src" / "kontext" / "project" / "jobs",
)

# Transitional allowlist for @job modules that still reach into the data
# layer. It must only ever shrink: route the access through a provider port
# (extending the port if needed) and delete the entry.
#
# `document_indexing_job.py` needs (a) a cursor-batched listing of non-deleted
# project files and (b) storage byte access, neither of which is on the
# file-service port yet.
KNOWN_JOB_DATA_OFFENDERS: frozenset[str] = frozenset(
    {
        "py/kontext-project/src/kontext/project/jobs/document_indexing_job.py",
    }
)


def _defines_job_class(path: Path) -> bool:
    """Return whether *path* declares a class decorated with ``@job``."""
    tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Name):
                if decorator.func.id == "job":
                    return True
            elif isinstance(decorator, ast.Name) and decorator.id == "job":
                return True
    return False


def _kontext_data_import_lines(path: Path) -> list[int]:
    """Return line numbers of any ``kontext.data`` import in *path*."""
    tree = ast.parse(path.read_text(encoding="utf-8"), str(path))
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "kontext.data" or node.module.startswith("kontext.data."):
                lines.append(node.lineno)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "kontext.data" or alias.name.startswith("kontext.data."):
                    lines.append(node.lineno)
    return lines


def test_job_definitions_do_not_import_the_data_layer() -> None:
    """@job modules must reach the platform through provider ports only.

    Job definitions run inside worker processes. In the local profile the
    worker happens to share SQLite with the API, but in a hosted profile the
    same job body must run against an API-backed provider. A `kontext.data`
    import inside a job defeats that portability, which is the invariant this
    test protects. (API-side dispatch helpers may live in the same directory;
    they are excluded because they declare no ``@job`` class.)
    """
    offenders: set[str] = set()
    missing_dirs: list[str] = []
    for job_dir in JOB_DEFINITION_DIRS:
        if not job_dir.is_dir():
            missing_dirs.append(str(job_dir.relative_to(REPO_ROOT)))
            continue
        for path in sorted(job_dir.rglob("*.py")):
            if not _defines_job_class(path):
                continue
            if _kontext_data_import_lines(path):
                offenders.add(str(path.relative_to(REPO_ROOT)))
    assert not missing_dirs, "Job definition directories are missing: " + ", ".join(missing_dirs)
    unexpected = offenders - set(KNOWN_JOB_DATA_OFFENDERS)
    assert not unexpected, (
        "@job modules must not import kontext.data; route access through a "
        "provider port: " + ", ".join(sorted(unexpected))
    )
    stale = set(KNOWN_JOB_DATA_OFFENDERS) - offenders
    assert not stale, "Stale KNOWN_JOB_DATA_OFFENDERS entries: " + ", ".join(sorted(stale))
