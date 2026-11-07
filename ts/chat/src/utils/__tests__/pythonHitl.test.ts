/// <reference types="jest" />

import { AgentToolNames, type SimpleRunEvent } from "@kontext-tech/schema";
import {
   createPythonHitlResolver,
   type NotebookHitlPort,
   type PythonHitlPorts
} from "../../pythonHitl";

type ToolOutputLike = {
   toolCallId?: string;
   toolName?: string;
   toolCallError?: string;
   result?: { success: boolean; targetType?: string; error?: string };
};

const pauseEvent = (
   toolCalls: Array<Record<string, unknown>>
): SimpleRunEvent =>
   ({ eventData: { toolCalls } }) as unknown as SimpleRunEvent;

const scriptToolCall = (
   code: string,
   toolCallId = "call-1"
): Record<string, unknown> => ({
   toolCallId,
   toolName: AgentToolNames.executePythonScript,
   toolArgs: { code }
});

const notebookToolCall = (
   args: Record<string, unknown>
): Record<string, unknown> => ({
   toolCallId: "call-nb",
   toolName: AgentToolNames.executePythonCode,
   toolArgs: args
});

const notebookPort = (): NotebookHitlPort => ({
   getCodeBlock: (blockId: string) => ({
      data: { code: `# code for ${blockId}` }
   }),
   markBlockExecuting: jest.fn(),
   writeOutputs: jest.fn(),
   markFailureTextOutput: jest.fn(),
   getDocument: () => ({ blocks: [] })
});

interface PortsOptions {
   approvalMode?: "always_ask" | "auto_approve";
   approved?: boolean;
   reason?: string;
   autoApproveFutureRuns?: boolean;
}

const makePorts = (options: PortsOptions = {}): PythonHitlPorts => {
   const {
      approvalMode,
      approved = true,
      reason,
      autoApproveFutureRuns
   } = options;

   return {
      approvalMode,
      getCurrentApprovalMode: jest.fn(),
      requestApproval: jest.fn().mockResolvedValue(
         approved
            ? {
                 approved: true,
                 ...(autoApproveFutureRuns ? { autoApproveFutureRuns } : {})
              }
            : { approved: false, reason }
      ),
      onAutoApproveFutureRuns: jest.fn(),
      executeSessionPython: jest.fn().mockResolvedValue({
         succeed: true,
         data: {
            success: true,
            message: "Executed",
            targetType: "session",
            outputs: []
         },
         error: {}
      }),
      executeNotebookPython: jest.fn().mockResolvedValue({
         succeed: true,
         data: {
            success: true,
            message: "Executed",
            targetType: "notebook",
            executionMode: "draft",
            outputs: []
         },
         error: {}
      }),
      saveNotebook: jest.fn(),
      notebook: notebookPort()
   };
};

describe("createPythonHitlResolver", () => {
   it("ignores non-pause events", async () => {
      const resolver = createPythonHitlResolver(makePorts());
      const result = await resolver({} as unknown as SimpleRunEvent);
      expect(result).toBeUndefined();
   });

   it("auto-approves session script when the mode says so", async () => {
      const hitlPorts = makePorts({ approvalMode: "auto_approve" });
      const resolver = createPythonHitlResolver(hitlPorts);

      const outputs = await resolver(pauseEvent([scriptToolCall("print(1)")]));

      expect(hitlPorts.requestApproval).not.toHaveBeenCalled();
      expect(outputs).toHaveLength(1);
      expect((outputs[0] as unknown as ToolOutputLike).result?.success).toBe(
         true
      );
   });

   it("rejects session script without an approval UI", async () => {
      const hitlPorts = makePorts();
      hitlPorts.requestApproval = undefined;
      const resolver = createPythonHitlResolver(hitlPorts);

      const outputs = await resolver(pauseEvent([scriptToolCall("print(1)")]));

      const output = outputs[0] as unknown as ToolOutputLike;
      expect(output.toolCallError).toContain("approval UI is not available");
      expect(output.result?.success).toBe(false);
      expect(output.result?.targetType).toBe("session");
   });

   it("propagates a rejected approval decision", async () => {
      const hitlPorts = makePorts({
         approved: false,
         reason: "user said not yet"
      });
      const resolver = createPythonHitlResolver(hitlPorts);

      const outputs = await resolver(pauseEvent([scriptToolCall("print(1)")]));

      expect(hitlPorts.executeSessionPython).not.toHaveBeenCalled();
      const output = outputs[0] as unknown as ToolOutputLike;
      expect(output.toolCallError).toBe("user said not yet");
      expect(output.result?.error).toBe("user said not yet");
   });

   it("remembers auto-approve when the user opts in", async () => {
      const hitlPorts = makePorts({ autoApproveFutureRuns: true });
      const resolver = createPythonHitlResolver(hitlPorts);

      await resolver(pauseEvent([scriptToolCall("print(1)")]));

      expect(hitlPorts.onAutoApproveFutureRuns).toHaveBeenCalledWith(
         "auto_approve"
      );
   });

   it("reports session execution failures as tool errors", async () => {
      const hitlPorts = makePorts();
      hitlPorts.executeSessionPython = jest.fn().mockResolvedValue({
         succeed: false,
         error: { messages: ["kernel died"] }
      });
      const resolver = createPythonHitlResolver(hitlPorts);

      const outputs = await resolver(pauseEvent([scriptToolCall("print(1)")]));

      expect((outputs[0] as unknown as ToolOutputLike).toolCallError).toBe(
         "kernel died"
      );
   });

   it("rejects a session script with empty code", async () => {
      const resolver = createPythonHitlResolver(makePorts());
      const outputs = await resolver(pauseEvent([scriptToolCall("   ")]));
      expect((outputs[0] as unknown as ToolOutputLike).toolCallError).toBe(
         "Missing code parameter"
      );
   });

   it("reports missing notebook_id / block_id parameters", async () => {
      const resolver = createPythonHitlResolver(makePorts());

      const missingNotebook = await resolver(
         pauseEvent([notebookToolCall({ block_id: "b" })])
      );
      const missingBlock = await resolver(
         pauseEvent([notebookToolCall({ notebook_id: "nb-1" })])
      );

      expect(
         (missingNotebook[0] as unknown as ToolOutputLike).toolCallError
      ).toBe("Missing notebook_id parameter");
      expect((missingBlock[0] as unknown as ToolOutputLike).toolCallError).toBe(
         "Missing block_id parameter"
      );
   });

   it("executes a notebook block, writes outputs and saves", async () => {
      const hitlPorts = makePorts({ approvalMode: "auto_approve" });
      const resolver = createPythonHitlResolver(hitlPorts);

      const outputs = await resolver(
         pauseEvent([
            notebookToolCall({ notebook_id: "nb-1", block_id: "block-9" })
         ])
      );

      expect(hitlPorts.notebook.markBlockExecuting).toHaveBeenCalledWith(
         "block-9",
         "notebook-nb-1"
      );
      expect(hitlPorts.notebook.writeOutputs).toHaveBeenCalled();
      expect(hitlPorts.saveNotebook).toHaveBeenCalledWith("nb-1", {
         blocks: []
      });
      expect((outputs[0] as unknown as ToolOutputLike).result?.success).toBe(
         true
      );
   });

   it("marks the block failed when notebook execution throws", async () => {
      const hitlPorts = makePorts();
      const notebook = notebookPort();
      hitlPorts.notebook = notebook;
      hitlPorts.executeNotebookPython = jest
         .fn()
         .mockRejectedValue(new Error("kernel exploded"));
      const resolver = createPythonHitlResolver(hitlPorts);

      const outputs = await resolver(
         pauseEvent([
            notebookToolCall({ notebook_id: "nb-1", block_id: "block-1" })
         ])
      );

      expect(notebook.markFailureTextOutput).toHaveBeenCalledWith(
         "block-1",
         "notebook-nb-1",
         "kernel exploded"
      );
      expect((outputs[0] as unknown as ToolOutputLike).toolCallError).toBe(
         "kernel exploded"
      );
   });

   it("tolerates a notebook save failure", async () => {
      const hitlPorts = makePorts({ approvalMode: "auto_approve" });
      hitlPorts.saveNotebook = jest
         .fn()
         .mockRejectedValue(new Error("save failed"));
      const resolver = createPythonHitlResolver(hitlPorts);

      const outputs = await resolver(
         pauseEvent([
            notebookToolCall({ notebook_id: "nb-1", block_id: "block-1" })
         ])
      );

      expect((outputs[0] as unknown as ToolOutputLike).result?.success).toBe(
         true
      );
   });

   it("prefers the code override over the block's stored code", async () => {
      const hitlPorts = makePorts({ approvalMode: "auto_approve" });
      const resolver = createPythonHitlResolver(hitlPorts);

      await resolver(
         pauseEvent([
            notebookToolCall({
               notebook_id: "nb-1",
               block_id: "block-1",
               code: "print(override)"
            })
         ])
      );

      expect(hitlPorts.executeNotebookPython).toHaveBeenCalledWith(
         "nb-1",
         "block-1",
         "print(override)"
      );
   });

   it("resolves multiple paused tool calls in one pause", async () => {
      const hitlPorts = makePorts({ approvalMode: "auto_approve" });
      const resolver = createPythonHitlResolver(hitlPorts);

      const outputs = await resolver(
         pauseEvent([
            scriptToolCall("print(1)", "call-a"),
            scriptToolCall("print(2)", "call-b")
         ])
      );

      expect(outputs).toHaveLength(2);
      expect(hitlPorts.executeSessionPython).toHaveBeenCalledTimes(2);
   });

   it("does not forward blank tool-arg code as an override", async () => {
      // Agents often pass code:"" meaning "run the stored block". Forwarding
      // that as codeOverride would make the backend treat the run as a draft
      // and skip recording the block's execution state.
      const hitlPorts = makePorts({ approvalMode: "auto_approve" });
      const resolver = createPythonHitlResolver(hitlPorts);

      await resolver(
         pauseEvent([
            notebookToolCall({
               notebook_id: "nb-1",
               block_id: "block-1",
               code: ""
            })
         ])
      );

      expect(hitlPorts.executeNotebookPython).toHaveBeenCalledWith(
         "nb-1",
         "block-1",
         undefined
      );
   });

   it("skips the client-side save when the backend recorded the state", async () => {
      const hitlPorts = makePorts({ approvalMode: "auto_approve" });
      hitlPorts.executeNotebookPython = jest.fn().mockResolvedValue({
         succeed: true,
         data: {
            success: true,
            message: "Executed",
            targetType: "notebook",
            executionMode: "persisted",
            outputs: []
         },
         error: {}
      });
      const resolver = createPythonHitlResolver(hitlPorts);

      await resolver(
         pauseEvent([
            notebookToolCall({ notebook_id: "nb-1", block_id: "block-1" })
         ])
      );

      expect(hitlPorts.executeNotebookPython).toHaveBeenCalledWith(
         "nb-1",
         "block-1",
         undefined
      );
      expect(hitlPorts.notebook.writeOutputs).toHaveBeenCalled();
      expect(hitlPorts.saveNotebook).not.toHaveBeenCalled();
   });
});
