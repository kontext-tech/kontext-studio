# kontext-harness-agno

Agno-backed harness adapter for Kontext agents.

This package is the optional distribution that registers the in-repo Agno
harness through the `kontext.agent_harnesses` entry-point group
(`agno = kontext.harness.agno.factory:AgnoAgentFrameworkAdapter`). It owns the
entire Agno SDK surface — the adapter never leaks `agno` imports into the
neutral layers:

- `kontext.agent` — neutral agent contracts (specs, toolkits, systems, tools)
- `kontext-agentic` — harness-neutral blueprints, domain tools, and chat workflows

Composition roots (`kontext-studio`, `kontext-api`) install this package to
select the Agno harness; a future ADK distribution would register under the
same entry-point group and become selectable via `KONTEXT_AGENT_FRAMEWORK`
without changes to the neutral layers. See `docs/ai/harness-abstraction.md`.

## Verification

```bash
uv run --package kontext-harness-agno pytest py/kontext-harness-agno/tests
bash scripts/run-pyright.sh py/kontext-harness-agno
```
