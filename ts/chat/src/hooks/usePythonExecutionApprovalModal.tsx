import type { PendingPythonExecutionRequest } from "@kontext-tech/schema";
import { Checkbox, Flex, theme, Typography } from "antd";
import { useUiApp } from "@kontext-tech/ui";
import React from "react";
import {
   loadRememberedPythonApprovalMode,
   persistRememberedPythonApprovalMode
} from "../utils/pythonApprovalStorage";

export interface PythonExecutionApprovalDecision {
   approved: boolean;
   reason?: string;
   autoApproveFutureRuns?: boolean;
}

const { useToken } = theme;

// Re-exported for convenience: existing consumers import from this module.
export {
   loadRememberedPythonApprovalMode,
   persistRememberedPythonApprovalMode
};

/**
 * Modal-driven approval resolver for Python execution requests.
 *
 * Returns a stable callback suitable for `useChat`'s
 * `requestPythonExecutionApproval` option so any single `useChat` instance
 * (page-level or component-level) can obtain an approval decision.
 */
export function usePythonExecutionApprovalModal(): (
   request: PendingPythonExecutionRequest
) => Promise<PythonExecutionApprovalDecision> {
   const { token } = useToken();
   const { modal } = useUiApp();

   return React.useCallback(
      (request: PendingPythonExecutionRequest) =>
         new Promise<PythonExecutionApprovalDecision>((resolve) => {
            let autoApproveFutureRuns = false;
            modal.confirm({
               title: "Review Python execution",
               okText: "Approve",
               cancelText: "Reject",
               width: 720,
               content: (
                  <Flex vertical gap="middle">
                     <Typography.Text type="secondary">
                        {request.targetType === "notebook"
                           ? `Notebook block ${request.blockId || "unknown"} in ${request.notebookId || "unknown notebook"}`
                           : "Session-scoped Python execution"}
                     </Typography.Text>
                     {request.targetType === "session" && (
                        <Typography.Text type="secondary">
                           Uses the data tables currently linked to this chat
                           session.
                        </Typography.Text>
                     )}
                     <pre
                        style={{
                           margin: 0,
                           padding: 12,
                           maxHeight: 320,
                           overflow: "auto",
                           whiteSpace: "pre-wrap",
                           background: token.colorFillAlter,
                           borderRadius: token.borderRadius
                        }}
                     >
                        {request.code}
                     </pre>
                     <Checkbox
                        onChange={(event) => {
                           autoApproveFutureRuns = event.target.checked;
                        }}
                     >
                        Auto-approve future runs in this chat
                     </Checkbox>
                  </Flex>
               ),
               onOk: () => {
                  resolve({ approved: true, autoApproveFutureRuns });
               },
               onCancel: () => {
                  resolve({
                     approved: false,
                     reason: "Python execution rejected by user."
                  });
               }
            });
         }),
      [modal, token.colorFillAlter, token.borderRadius]
   );
}
