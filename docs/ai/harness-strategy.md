# Harness strategy: decision record

Status: **stay on Agno as the default harness.** Evaluated in 2026-10/11 as a
preemptive review, not a response to an incident. The mechanics of the
abstraction live in [Harness abstraction](harness-abstraction.md); this record
keeps the decision and the conditions that would reopen it.

## Why the decision was worth reviewing

`py/kontext-harness-agno` is about 3.1k lines of adapter code plus 1.8k lines of
tests. Agno provides four things the product consumes:

- the agent loop and tool calling (all tools are first-party `KontextToolkit`s;
  no Agno built-in toolkits are used);
- `Team` orchestration: a coordinator, specialist members, shared session
  state, and member event streaming;
- provider client classes (construction only; provider policy lives in
  `kontext-llm`);
- the pause/resume requirement model behind human-in-the-loop tool execution.

The integration is deep on three seams only:

1. **Persisted HITL interrupts.** External-execution tools pause a run, and the
   requirement state is persisted so recovery survives process restarts.
2. **Streaming event translation.** Agno's event types are mapped onto the
   neutral `SimpleRunEvent`, including member activity.
3. **Shared mutable team state.** `SharedSessionStore` lets specialists exchange
   artifact and table handles.

Known frictions are adapter-owned and tolerable: Agno's async surface still runs
sync internals, so the adapter bridges a thread pool into the event loop, and a
few upstream behaviors need small workarounds. Framework churn lands in four
adapter modules, not in the domain layer.

## Options considered

Scored against the three seams, as of 2026-10:

| Option | HITL persist + resume | Async-native streaming | Shared-state multi-agent | Verdict |
| --- | --- | --- | --- | --- |
| **Stay on Agno** | existing | bridge tax | existing | chosen |
| DIY `kontext-harness-core` | simple | yes | buildable | viable fallback |
| Pydantic AI | maps closely | yes | buildable | best alternative if forced |
| LangGraph | checkpoint-based | yes | hand-built graph | too much ceremony |
| OpenAI Agents SDK | serializable run state | yes | handoffs, not shared workers | OpenAI-first |
| Google ADK | yes | yes | native | cloud-flavored for a local-first product |
| smolagents | none | yes | none | would require building the rest |

The provider picture also improved: Bedrock and Gemini/Vertex are reachable
through OpenAI-compatible endpoints, so a non-Agno path would not need a native
SDK per provider. Anthropic-native features remain the main fidelity question.

## Why staying is the right default

- There is no acute pain: no production breakage, fidelity incident, or
  performance problem.
- The abstraction has already proved itself. A swap is a composition change, and
  the neutral contracts make waiting cheap.
- The hard semantics — persistence, streaming policy, delegation behavior, tool
  schemas — now live in neutral layers. That strengthens the DIY option rather
  than making it urgent.

## Neutral layer now in place

- **Agent contracts:** `AgentSpec`, `AgentKind`, `BaseAgenticSystem`,
  `AgentFrameworkAdapter`, and blueprint/harness registries.
- **Tool contract:** neutral tool metadata and a schema renderer, with the
  adapter owning only native construction.
- **Persistence:** `SessionPersistence` in `kontext-agent`, implemented by
  `kontext-data` as `agent_run_messages` (wire-shaped history) and
  `agent_harness_states` (opaque per-session blob). The adapter's Agno SQLite
  file is retired; deleting a chat cascades both tables.
- **Streaming:** neutral `SimpleRunEvent` vocabulary plus `EventBuffer` and
  `BoundedEventQueue` in `kontext-agent`.
- **Delegation contract:** member visibility, history, persisted output, and
  shared state are defined as observable behavior and pinned by the conformance
  suite.
- **Tests:** neutral tests no longer import Agno internals; the adapter runs the
  neutral conformance scenarios.

## Deliberately deferred

- **Provider one-client consolidation.** Introduce a neutral `ModelClient` port
  only when a second runtime client exists.
- **Per-project harness selection.** Keep `KONTEXT_AGENT_FRAMEWORK`
  process-global until two adapters actually coexist.
- **DIY or alternative harness.** Revisit only when a trigger below fires.

## Re-trigger conditions

1. **Agno churn bites:** an upgrade whose adapter rework exceeds the DIY build
   cost, or repeated sync/workaround incidents.
2. **Fidelity need:** product requirements depend on run internals the framework
   does not expose, such as durable crash-resume of long analyses.
3. **Durable workflows:** long-running workflow durability becomes a roadmap
   item; evaluate Pydantic AI with a durable engine before building it.
4. **DIY economics:** the conformance suite shows the owned harness core is
   smaller than the cost of keeping the adapter.
5. **Provider reality:** a customer requires native Bedrock/Vertex features such
   as IAM-only auth or provisioned throughput.

Review this record when a trigger fires or at the next harness-adjacent epic,
not on a calendar.

## Explicitly out of scope

- Harness-managed memory or learning subsystems.
- Harness-managed knowledge/RAG; Kontext knowledge is an OKF domain tool.
- Harness workflow engines, MCP stacks, built-in toolkits, and eval tables.
- Server-side model gateways; client-side execution stays the HITL contract.

## Related documentation

- [Harness abstraction](harness-abstraction.md) — the boundary, composition
  contract, streaming contract, and storage rules.
- [AI architecture](ai-architecture.md) — agents, tools, and the request path.
- [Model provider configuration](model-provider-configuration.md) — how
  provider selection becomes a harness-neutral model binding.
- [Tool result schemas](tool-results-schema.md) — the shared tool-result
  contract.
