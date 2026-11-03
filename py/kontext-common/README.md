# Kontext Common

Shared contracts and cross-cutting primitives for Kontext Python components.

This package is the dependency leaf of the workspace: nothing above it may be
imported here. It is organised by concern:

| Area | Contains |
| --- | --- |
| `protocols/` | One module per domain of operation-level service contracts (`files`, `catalog`, `query`, `project`, `chat`, `agent`, `jobs`, `execution`, `knowledge`, `profiling`) plus capability/provider surfaces in `providers.py` |
| `query/` | Engine port (`engine.py`), result policy, and session primitives (`session_storage`, `session_compatibility`, `session_locks`, `session_scope`) |
| `python_execution/` | Managed Python execution contracts (`runner.py`), code policy (`policy.py`), helper detectors, and kernel identity |
| `knowledge/` | Provider-neutral knowledge-index contracts (`index.py`) |
| `contracts/` | Shared runtime data contracts (`AgentConfig`, `ModelRuntime`, `ResolvedModelConfig`) |
| `pydantic.py` | Shared Pydantic bases (`KontextBaseModel`, `CamelCaseModel`, `PascalModel`) |
| `constants/` | Env vars, task profiles, site features, query constants |
| `config.py`, `logging.py`, `exceptions.py`, `messaging.py`, `pagination.py`, `project_scoped.py` | Cross-cutting infrastructure |
| `catalog/` | `connector_specs.py` and `revision.py` — pure catalog helpers shared by catalog, data, engine, and query |
| `artifacts/` | `sequencing.py` and `provenance.py` — shared artifact action/provenance helpers |
| `jobs/` | `scheduling.py`, `transport.py`, and `trigger_actor.py` — shared job primitives |
| `notebook_aliases.py`, `utils/` | Notebook alias binding and generic utilities (dates, enums, environment, storage paths, JSON, async polling) |

The public facades (`kontext.common`, `kontext.common.protocols`,
`kontext.common.query`, `kontext.common.utils`) are **lazy**: importing one
helper does not load the rest of the package. Prefer importing from the
submodule that owns a symbol when the intent is clearer.
