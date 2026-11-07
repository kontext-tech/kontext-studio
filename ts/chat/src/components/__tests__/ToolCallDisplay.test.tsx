/// <reference types="jest" />

import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ChatToolCallSegment } from "../../types/chat";
import ToolCallDisplay from "../ToolCallDisplay";

jest.mock("@ant-design/x", () => {
   const React = jest.requireActual<typeof import("react")>("react");

   return {
      CodeHighlighter: ({ children }: { children: React.ReactNode }) =>
         React.createElement("pre", null, children)
   };
});

jest.mock("@kontext-tech/icons", () => {
   const React = jest.requireActual<typeof import("react")>("react");

   const StubIcon = ({ "data-testid": testId }: { "data-testid"?: string }) =>
      React.createElement("span", { "data-testid": testId ?? "icon" });

   return {
      CheckOutlined: () =>
         React.createElement(StubIcon, { "data-testid": "check-icon" }),
      CloseOutlined: () =>
         React.createElement(StubIcon, { "data-testid": "close-icon" }),
      LoadingOutlined: () =>
         React.createElement(StubIcon, { "data-testid": "loading-icon" }),
      RightOutlined: () =>
         React.createElement(StubIcon, { "data-testid": "right-icon" })
   };
});

jest.mock("../MarkdownRenderer", () => {
   const React = jest.requireActual<typeof import("react")>("react");

   return {
      __esModule: true,
      default: ({ content }: { content: string }) =>
         React.createElement(
            "div",
            { "data-testid": "markdown-renderer" },
            content
         )
   };
});

const makeToolCall = (
   overrides: Partial<ChatToolCallSegment> = {}
): ChatToolCallSegment =>
   ({
      segmentType: "tool_call",
      cid: "segment-1",
      parentId: null,
      toolCallId: "tool-call-1",
      toolName: "execute_python_code",
      toolArgs: {},
      toolCallError: null,
      result: null,
      status: "completed",
      error: null,
      ...overrides
   }) as ChatToolCallSegment;

describe("ToolCallDisplay", () => {
   it("renders tool arguments with ellipsis-friendly rows", () => {
      const toolCall = makeToolCall({
         toolArgs: {
            notebook_id: "nb-123",
            runtime: {
               profile: "managed"
            },
            packages: ["numpy", "pandas"],
            code: "print('hello')",
            empty_value: ""
         }
      });

      render(<ToolCallDisplay toolCall={toolCall} allSegments={[toolCall]} />);

      fireEvent.click(screen.getByRole("button"));

      expect(screen.getByText("Arguments")).toBeInTheDocument();
      expect(screen.getByText("notebook_id")).toHaveAttribute(
         "title",
         "notebook_id"
      );
      expect(screen.getByText("nb-123")).toHaveAttribute("title", "nb-123");
      expect(screen.getByText("runtime.profile")).toBeInTheDocument();
      expect(screen.getByText("managed")).toBeInTheDocument();
      expect(screen.getByText("packages[0]")).toBeInTheDocument();
      expect(screen.getByText("numpy")).toBeInTheDocument();
      expect(screen.getByText("packages[1]")).toBeInTheDocument();
      expect(screen.getByText("pandas")).toBeInTheDocument();
      expect(screen.getByText("empty_value")).toBeInTheDocument();
      expect(screen.getByText('""')).toBeInTheDocument();
      expect(screen.getByText("code")).toBeInTheDocument();
      expect(screen.getByText("print('hello')")).toHaveStyle({
         overflow: "hidden",
         textOverflow: "ellipsis",
         whiteSpace: "nowrap"
      });
   });

   it("auto-expands delegation calls and shows flattened delegation arguments", () => {
      const toolCall = makeToolCall({
         toolName: "delegate_task_to_member",
         status: "started",
         toolArgs: {
            member_id: "notebook_agent",
            transfer: {
               notebook_id: "nb-456",
               block_id: "block-789"
            }
         }
      });

      render(<ToolCallDisplay toolCall={toolCall} allSegments={[toolCall]} />);

      expect(
         screen.getByText("Run Sub Agent: notebook_agent")
      ).toBeInTheDocument();
      expect(screen.getByText("member_id")).toBeInTheDocument();
      expect(screen.getByText("notebook_agent")).toBeInTheDocument();
      expect(screen.getByText("transfer.notebook_id")).toBeInTheDocument();
      expect(screen.getByText("nb-456")).toBeInTheDocument();
      expect(screen.getByText("transfer.block_id")).toBeInTheDocument();
      expect(screen.getByText("block-789")).toBeInTheDocument();
   });
});
