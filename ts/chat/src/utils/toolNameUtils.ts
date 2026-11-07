import {
   AgentToolNames,
   DelegationToolNames,
   ExternalExecutionToolNames
} from "@kontext-tech/schema";

const TOOL_NAME_OVERRIDES: Record<string, string> = {
   [AgentToolNames.executePythonCode]: "Execute Python Code",
   [AgentToolNames.executePythonScript]: "Execute Python Script",
   [AgentToolNames.delegateTaskToMember]: "Run Sub Agent",
   [AgentToolNames.delegateTaskToMembers]: "Run Sub Agents",
   // Delegation display titles some payloads emit instead of the ids.
   run_sub_agent: "Run Sub Agent",
   run_sub_agents: "Run Sub Agents"
};

// Only titles whose display contains "Sub Agent" qualify as delegation via
// the overrides map: that map also holds non-delegation display names (e.g.
// the external execution Python tools), which must never be classified as
// sub-agent executions.
const subAgentTitlePattern = /sub agent/i;

const normalizeToolName = (value: string): string =>
   value.trim().toLowerCase().replace(/\s+/g, "_");

const toTitleCase = (value: string): string => {
   const parts = value
      .trim()
      .replace(/[._-]+/g, " ")
      .split(" ")
      .filter(Boolean);

   return parts
      .map((part) => {
         const lower = part.toLowerCase();
         return lower.length ? lower[0].toUpperCase() + lower.slice(1) : lower;
      })
      .join(" ");
};

/**
 * Checks if a tool name is a sub-agent delegation tool (canonical harness
 * contract names and their display titles — see
 * `ts/schema/src/ai/tool-names.ts`).
 * External execution (HITL Python) tools are explicitly not delegation.
 */
export const isDelegationTool = (
   toolName: string | null | undefined
): boolean => {
   if (!toolName) return false;
   const normalized = normalizeToolName(toolName);
   const isDelegation =
      DelegationToolNames.includes(normalized) ||
      (TOOL_NAME_OVERRIDES[normalized] ?? "").match(subAgentTitlePattern) !==
         null;
   return isDelegation;
};

/**
 * Convert a tool identifier (often snake_case) into a user-friendly display name.
 * Keeps already-human-readable names intact.
 */
export const getToolDisplayName = (
   toolName: string | null | undefined
): string => {
   if (!toolName) return "Unknown tool";

   const trimmed = toolName.trim();
   if (!trimmed) return "Unknown tool";

   const override = TOOL_NAME_OVERRIDES[normalizeToolName(trimmed)];
   if (override) return override;

   // If it's already a readable label, keep it.
   if (trimmed.includes(" ") && /[A-Z]/.test(trimmed)) {
      return trimmed;
   }

   return toTitleCase(trimmed);
};

/**
 * Checks if a tool name is one of the externally-executed (HITL) Python tools.
 */
export const isExternalExecutionTool = (
   toolName: string | null | undefined
): boolean => {
   if (!toolName) return false;
   return ExternalExecutionToolNames.includes(normalizeToolName(toolName));
};
