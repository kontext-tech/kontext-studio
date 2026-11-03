# Kontext Agentic

Harness-neutral agent application layer: blueprints, domain tools, and the chat workflow for Kontext.

## Package Role

The agent stack is split by direction of dependency; adapters are optional packages.

- `kontext-agent`: framework-neutral contracts — the harness SPI
  (`AgentCreationContext`, `AgentFrameworkAdapter`, entry-point registry),
  `AgentSpec`/`AgentKind`, `BaseAgenticSystem` port, toolkit/tool-metadata
  registry (`ToolMeta`), execution contexts and the tool-result sidecar port,
  shared session store, run-state persistence port
- `kontext-chat`: chat-session domain (sessions, token usage) plus the workflow/factory
  protocols chat glue implements
- `kontext-llm`: model/provider registry and resolution
- `kontext-agentic`: this package — blueprint spec builders, domain tools, and the chat
  workflow implementation (`ChatHandler`); imports the contracts, never a harness
- `kontext-harness-agno`: optional Agno adapter distribution registering through the
  `kontext.agent_harnesses` entry-point group (see `docs/ai/harness-abstraction.md`)

## Main Areas

- `kontext.agentic.blueprints`: domain blueprint builders (SQL, chart, notebook, python, coordinator) and the registry wiring (kind -> builder)
- `kontext.agentic.tools`: Kontext data/artifact tools built on the neutral tool contracts
- `kontext.agentic.chat_handler` / `kontext.agentic.chat_context`: the `kontext-chat` workflow
  implementation and agent-creation context assembly
- `kontext.agentic.adapters`: blueprint registry and the `create_agentic_system`
  composition (harness resolution lives in `kontext.agent.harness`)
- `kontext.agentic.utils`: configuration and small AI-specific helpers

## Agent Runtime Defaults

Use `AgentConfigBuilder` for agent runtime defaults:

```python
from kontext.agentic import AgentConfig, AgentConfigBuilder

config = AgentConfigBuilder.from_runtime_provider(
    runtime_provider=runtime_provider,
    task_profile="chat_planning",
    reasoning_effort="high",  # optional; a persisted selection still wins
)

explicit = AgentConfig(markdown=True, tool_call_limit=20)
```

`AgentConfig` is behaviour-only. Model identity lives in a `ModelRuntime`
(`ResolvedModelConfig` binding + run credentials) resolved by composition and
carried on `AgentCreationContext.model`. Model/provider construction lives in
the harness (e.g. `kontext.harness.agno.models`), with provider metadata from
`kontext-llm`.

## Harness Boundary

Only a harness adapter distribution imports a harness SDK (enforced by
`test_only_the_harness_adapter_imports_a_harness_sdk`): tools are framework-agnostic,
tool metadata lives in `kontext-agent`, and Agno adaptation happens in
`kontext-harness-agno`. Future ADK or LangGraph distributions register the same
entry-point group without touching the neutral layers.

Agno event translation lives in `kontext.harness.agno.event_converters`, where
framework events are mapped into Kontext `SimpleRunEvent` payloads and
normalized according to client visibility policy.

## Development

```bash
uv sync --group dev
uv run pytest
```
