# Kontext Agent

Framework-agnostic agent core primitives for Kontext.

## Responsibilities

- base agent runtime contract (`BaseAgenticSystem`)
- harness SPI (`AgentCreationContext`, `AgentFrameworkAdapter`, the
  `kontext.agent_harnesses` entry-point registry, logger seeding)
- neutral run-state persistence port (`SessionPersistence`)
- tool runtime metadata and toolkit container abstractions
- session/tool execution context helpers
- tool-result sidecar and session-state helpers
- neutral streaming policy (`EventBuffer`, `BoundedEventQueue`) and client
  visibility policy
- tool metadata registry and artifact-oriented decorators
- the conformance suite (`kontext.agent.conformance`, imported explicitly)

## Non-Goals

`kontext-agent` should not know about Agno, LangGraph, ADK, or any other
concrete runtime, and it must not depend on the application layer
(`kontext-agentic`), chat, or storage. Framework-specific adapters are separate
distributions (`kontext-harness-*`) that implement the harness SPI from this
package.

The harness SPI references the shared `kontext-common` `ResolvedModelConfig`
binding; this package never wires or resolves models.
