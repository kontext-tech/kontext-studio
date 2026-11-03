/// <reference types="jest" />

import {
   AgentToolNames,
   DelegationToolNames,
   ExternalExecutionToolNames
} from "@kontext-labs/schema";
import {
   getToolDisplayName,
   isDelegationTool,
   isExternalExecutionTool
} from "../toolNameUtils";

describe("isDelegationTool", () => {
   it("matches the contract delegation names", () => {
      for (const name of DelegationToolNames) {
         expect(isDelegationTool(name)).toBe(true);
      }
   });

   it("matches delegation titles emitted instead of ids", () => {
      expect(isDelegationTool("Run Sub Agent")).toBe(true);
      expect(isDelegationTool("run sub agents")).toBe(true);
   });

   it("does not classify external execution (HITL) Python tools as delegation", () => {
      for (const name of ExternalExecutionToolNames) {
         expect(isDelegationTool(name)).toBe(false);
      }
      expect(isDelegationTool(AgentToolNames.executePythonCode)).toBe(false);
      expect(isDelegationTool(AgentToolNames.executePythonScript)).toBe(false);
      expect(isDelegationTool("Execute Python Code")).toBe(false);
   });

   it("rejects empty, unknown and whitespace-only names", () => {
      expect(isDelegationTool(null)).toBe(false);
      expect(isDelegationTool(undefined)).toBe(false);
      expect(isDelegationTool("")).toBe(false);
      expect(isDelegationTool("   ")).toBe(false);
      expect(isDelegationTool("execute_sql")).toBe(false);
   });
});

describe("isExternalExecutionTool", () => {
   it("matches the contract external-execution names", () => {
      for (const name of ExternalExecutionToolNames) {
         expect(isExternalExecutionTool(name)).toBe(true);
      }
   });

   it("tolerates display-title spacing", () => {
      expect(isExternalExecutionTool("execute python script")).toBe(true);
   });

   it("rejects non-HITL tools", () => {
      expect(isExternalExecutionTool(AgentToolNames.delegateTaskToMember)).toBe(
         false
      );
      expect(isExternalExecutionTool(null)).toBe(false);
   });
});

describe("getToolDisplayName", () => {
   it("uses override titles for contract tools", () => {
      expect(getToolDisplayName(AgentToolNames.executePythonCode)).toBe(
         "Execute Python Code"
      );
      expect(getToolDisplayName(AgentToolNames.delegateTaskToMembers)).toBe(
         "Run Sub Agents"
      );
   });

   it("falls back to title-casing snake_case names", () => {
      expect(getToolDisplayName("execute_sql")).toBe("Execute Sql");
   });

   it("keeps already readable names", () => {
      expect(getToolDisplayName("Run Code Analysis")).toBe("Run Code Analysis");
   });

   it("handles empty names", () => {
      expect(getToolDisplayName(null)).toBe("Unknown tool");
      expect(getToolDisplayName("")).toBe("Unknown tool");
   });
});
