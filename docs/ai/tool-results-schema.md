# Tool result schemas

Tool results cross the TypeScript/Python boundary, so they need one shared
shape. Kontext keeps that shape in two layers:

1. **Transport schemas** (Zod): the data structure sent between frontend and
   backend.
2. **Domain helpers** (Python): behavior built on the generated models, not a
   second copy of the data structure.

## Source of truth

`ts/schema/src/ai/tool-results.ts` defines the schemas:

```typescript
export const BaseToolResultSchema = z.object({
   success: z.boolean(),
   message: z.string()
});

export const PythonExecutionResultSchema =
   BaseToolResultSchema.extend({
      outputs: z.array(CodeExecutionOutputSchema).default([])
   });
```

`ToolCallResultSchema` is a flat union of every supported result type, with
`BaseToolResultSchema` last as the untyped fallback. It is deliberately not a
discriminated union: the OpenAPI exporter would wrap each member in an extra
model and force every consumer through `ToolCallResult.root`.

The Python models (`PythonExecutionResult`, `ToolCallResult`, and the rest) are
generated from the same OpenAPI spec into `kontext-schema`. See
[Generated code](../development/generated-code.md). `kontext-agentic` adds
helpers on top instead of redeclaring the models.

## Flow

External tool execution is a pause/resume round trip:

1. The agent pauses and emits a `RunPausedEvent` containing the pending
   `toolCalls`.
2. The frontend executes the tool (for example, Python via Pyodide), builds a
   typed result, and serializes it with `JSON.stringify`.
3. The frontend sends the tool call back with `result` as a JSON string.
4. The backend parses it with `ToolResultParser`, which validates the payload
   against the registered result type for that tool.
5. The adapter resumes the run with the validated result, and the result is
   serialized back to the model as JSON.

The `result` field on a `ToolCall` is a string, not an object, so every consumer
parses and validates at the boundary.

## Backend helpers

`py/kontext-agentic/src/kontext/agentic/utils/tool_result_utils.py` provides the
domain-layer operations:

- `tool_result_to_str` serializes a result to JSON for the model, preferring
  camelCase aliases and a model's `to_dict` when available.
- `tool_result_to_payload` produces the payload dict the frontend expects.
- `raise_for_tool_status` raises when a result reports failure.

`ToolResultParser` lives in `py/kontext-agent/src/kontext/agent/tools/registry.py`
and owns validation; the helpers never inspect raw JSON themselves.

## Design rules

- **Transport stays minimal.** Zod schemas describe data, not behavior.
- **Generated, not mirrored.** Python models come from the schema pipeline;
  hand-written Python code adds helpers, not parallel model classes.
- **One union, one fallback.** New result types are added to
  `ToolCallResultSchema` and the tool registry, so parsing stays uniform.
- **Python behavior stays Python.** Serialization and error-raising helpers
  live in the domain layer rather than leaking into generated models.

## Key files

| File | Role |
| --- | --- |
| `ts/schema/src/ai/tool-results.ts` | Zod schemas and the `ToolCallResult` union |
| `py/kontext-schema/src/kontext/schema/_generated/` | Generated Pydantic models |
| `py/kontext-agent/src/kontext/agent/tools/registry.py` | `ToolResultParser` and tool metadata |
| `py/kontext-agentic/src/kontext/agentic/utils/tool_result_utils.py` | Serialization and failure helpers |
| `py/kontext-harness-agno/src/kontext/harness/agno/system.py` | Pause/resume result handling |

## Related documentation

- [AI architecture](ai-architecture.md) — agents, tools, and the request flow.
- [Generated code](../development/generated-code.md) — how the shared models
  are produced.
