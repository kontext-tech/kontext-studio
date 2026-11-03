# Kontext LLM

Shared language model registry, provider definitions, and selection resolution
for Kontext.

## Modules

| Module | Responsibility |
| --- | --- |
| `model_connection_store.py` | `ModelConnectionStore` port + process-wide registration seam used by composition |
| `model_selection.py` | Resolve a persisted model selection to a `ResolvedModelConfig` binding, including run credentials |
| `provider_definitions.py` | Load `resources/models/model-provider-definitions.json` and derive provider lookup tables |
| `provider_resolution.py` | Resolve provider name, base URL, API key, and reasoning kwargs for a binding |
| `service.py` | `LanguageModelService`: foundation-model catalog + agent behaviour defaults |
| `resources/models/` | Committed foundation-model and provider-definition data |

Import the public surface from `kontext.llm`; import submodules directly only
when the narrower intent is clearer.

This package has no agent-framework imports. Model objects are constructed by
the active harness adapter.
