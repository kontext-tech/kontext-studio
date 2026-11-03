/**
 * Canonical agent tool-name contract shared with the backend
 * (`py/kontext-common/src/kontext/common/constants/tool_names.py` — keep in
 * sync). The frontend matches on these names for delegation nesting and the
 * Python HITL approval flow instead of hardcoding harness-specific strings.
 */

export const AgentToolNames = {
   delegateTaskToMember: "delegate_task_to_member",
   delegateTaskToMembers: "delegate_task_to_members",
   executePythonCode: "execute_python_code",
   executePythonScript: "execute_python_script"
} as const;

export const DelegationToolNames: readonly string[] = [
   AgentToolNames.delegateTaskToMember,
   AgentToolNames.delegateTaskToMembers
];

export const ExternalExecutionToolNames: readonly string[] = [
   AgentToolNames.executePythonCode,
   AgentToolNames.executePythonScript
] as const;
