/** @jest-environment jsdom */

import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { CodeBlockComponent, CodeBlockOutputs } from "./CodeBlockComponent";

const mockUpdateBlockData = jest.fn();
const mockExecuteCell = jest.fn();
const mockOnViewExecutionRun = jest.fn();

jest.mock("@kontext-tech/icons", () => {
   const React = jest.requireActual<typeof import("react")>("react");

   const Icon = ({ name }: { name: string }) =>
      React.createElement("span", { "data-testid": name }, name);

   return {
      CodeOutlined: () => React.createElement(Icon, { name: "code" }),
      DownOutlined: () => React.createElement(Icon, { name: "down" }),
      EyeOutlined: () => React.createElement(Icon, { name: "eye" }),
      InfoCircleOutlined: () => React.createElement(Icon, { name: "info" }),
      LoadingOutlined: () => React.createElement(Icon, { name: "loading" }),
      PlayCircleOutlined: () => React.createElement(Icon, { name: "play" }),
      StopOutlined: () => React.createElement(Icon, { name: "stop" }),
      UpOutlined: () => React.createElement(Icon, { name: "up" })
   };
});

jest.mock("@kontext-tech/theme", () => ({
   useTheme: () => ({
      isDarkMode: false
   })
}));

jest.mock("@kontext-tech/ui", () => ({
   LoadingSpinner: () => null
}));

jest.mock("antd", () => {
   const React = jest.requireActual<typeof import("react")>("react");

   const Button = ({
      children,
      onClick,
      disabled,
      icon,
      loading: _loading,
      ...props
   }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
      icon?: React.ReactNode;
      loading?: boolean;
   }) =>
      React.createElement(
         "button",
         { type: "button", onClick, disabled, ...props },
         icon,
         children
      );

   const Input = ({
      value,
      onChange,
      ...props
   }: React.InputHTMLAttributes<HTMLInputElement>) =>
      React.createElement("input", {
         ...props,
         value,
         onChange
      });

   return {
      Button,
      Input,
      Space: ({ children }: { children: React.ReactNode }) =>
         React.createElement("div", null, children),
      Tag: ({ children }: { children: React.ReactNode }) =>
         React.createElement("span", null, children),
      Tooltip: ({ children }: { children: React.ReactNode }) =>
         React.createElement(React.Fragment, null, children),
      theme: {
         useToken: () => ({
            token: {
               colorFillTertiary: "#eee",
               colorBgLayout: "#fff",
               colorText: "#111",
               colorTextSecondary: "#222",
               colorFillAlter: "#f5f5f5",
               borderRadius: 4,
               colorBorderSecondary: "#ddd",
               colorTextQuaternary: "#999",
               colorBorder: "#ddd",
               colorBgContainer: "#fff",
               colorLink: "#1677ff"
            }
         })
      }
   };
});

jest.mock("@notebook/components/code/LazyCodeEditor", () => {
   const React = jest.requireActual<typeof import("react")>("react");

   return {
      __esModule: true,
      default: ({
         value,
         onChange,
         onBlur
      }: {
         value: string;
         onChange?: (value: string) => void;
         onBlur?: () => void;
      }) =>
         React.createElement("textarea", {
            value,
            onChange: (event: React.ChangeEvent<HTMLTextAreaElement>) =>
               onChange?.(event.target.value),
            onBlur
         })
   };
});

jest.mock("@notebook/context/NotebookServiceContext", () => ({
   useNotebookServices: () => ({
      notebookId: "11111111-1111-1111-1111-111111111111",
      onViewExecutionRun: mockOnViewExecutionRun
   })
}));

jest.mock("@notebook/hooks/useExecuteCell", () => ({
   useExecuteCell: () => ({
      execute: mockExecuteCell,
      cancel: jest.fn().mockResolvedValue(false),
      isExecuting: false,
      result: null,
      setResult: jest.fn()
   })
}));

jest.mock("@notebook/stores/notebookStore", () => {
   const useNotebookStore = Object.assign(
      jest.fn(
         (selector: (state: { getCodeBlock: () => undefined }) => unknown) =>
            selector({
               getCodeBlock: () => undefined
            })
      ),
      {
         getState: () => ({
            updateBlockData: mockUpdateBlockData
         })
      }
   );

   return { useNotebookStore };
});

describe("CodeBlockComponent python execution", () => {
   beforeEach(() => {
      mockUpdateBlockData.mockReset();
      mockExecuteCell.mockReset();
      mockOnViewExecutionRun.mockReset();
   });

   it("executes the latest editor code without forcing a notebook save", async () => {
      mockExecuteCell.mockResolvedValue({
         status: "success",
         executionMode: "draft",
         executionRunId: "run-123",
         output: [
            {
               type: "text",
               mimeType: "text/plain",
               content: "done"
            }
         ]
      });

      const onChange = jest.fn();

      render(
         React.createElement(CodeBlockComponent, {
            id: "22222222-2222-2222-2222-222222222222",
            data: {
               code: "print('old')",
               language: "python",
               title: "",
               outputs: [],
               showCode: true
            },
            config: {
               instanceId: "33333333-3333-3333-3333-333333333333"
            },
            onChange
         })
      );

      fireEvent.change(screen.getAllByRole("textbox")[1]!, {
         target: { value: "print('new')" }
      });
      fireEvent.click(screen.getAllByRole("button")[0]!);

      await waitFor(() => {
         expect(mockExecuteCell).toHaveBeenCalledTimes(1);
      });

      expect(mockUpdateBlockData).toHaveBeenNthCalledWith(
         1,
         "22222222-2222-2222-2222-222222222222",
         expect.objectContaining({
            code: "print('new')",
            title: "",
            showCode: true
         }),
         "33333333-3333-3333-3333-333333333333"
      );
      expect(mockExecuteCell).toHaveBeenCalledWith("print('new')", {
         notebookId: "11111111-1111-1111-1111-111111111111",
         blockId: "22222222-2222-2222-2222-222222222222"
      });
      expect(screen.queryByText("draft run")).toBeNull();
      // The run link opens the job run details drawer inline instead of
      // navigating to the job runs page.
      fireEvent.click(await screen.findByText("Run details"));
      expect(mockOnViewExecutionRun).toHaveBeenCalledWith("run-123");
      expect(screen.getByLabelText("Execution info")).toBeTruthy();
   });

   it("shows a stop button while the cell is executing", async () => {
      // Never resolves: keeps the cell in the executing state.
      mockExecuteCell.mockReturnValue(new Promise(() => {}));

      render(
         React.createElement(CodeBlockComponent, {
            id: "22222222-2222-2222-2222-222222222222",
            data: {
               code: "print('hello')",
               language: "python",
               title: "",
               outputs: [],
               showCode: true
            },
            config: {
               instanceId: "33333333-3333-3333-3333-333333333333"
            },
            onChange: jest.fn()
         })
      );

      fireEvent.click(screen.getAllByRole("button")[0]!);

      await waitFor(() => {
         expect(mockExecuteCell).toHaveBeenCalledTimes(1);
      });

      // The stop control must remain reachable while execution is in flight.
      expect(screen.getByTestId("stop")).toBeTruthy();
   });

   it("shows an execution error in block output when Python execution fails", async () => {
      mockExecuteCell.mockResolvedValue({
         status: "error",
         error: "Execution failed"
      });

      render(
         React.createElement(CodeBlockComponent, {
            id: "22222222-2222-2222-2222-222222222222",
            data: {
               code: "print('hello')",
               language: "python",
               title: "",
               outputs: [],
               showCode: true
            },
            config: {
               instanceId: "33333333-3333-3333-3333-333333333333"
            },
            onChange: jest.fn()
         })
      );

      fireEvent.click(screen.getAllByRole("button")[0]!);

      await waitFor(() => {
         expect(mockExecuteCell).toHaveBeenCalledTimes(1);
      });

      expect(mockUpdateBlockData).toHaveBeenLastCalledWith(
         "22222222-2222-2222-2222-222222222222",
         expect.objectContaining({
            isExecuting: false,
            lastExecuted: expect.any(Number),
            outputs: [
               {
                  type: "text",
                  mimeType: "text/plain",
                  content: "Execution failed"
               }
            ]
         }),
         "33333333-3333-3333-3333-333333333333",
         { markDirty: false }
      );
      expect(await screen.findByText("Execution failed")).toBeTruthy();
   });

   it("renders Python before the optional title", () => {
      const { container } = render(
         React.createElement(CodeBlockComponent, {
            id: "22222222-2222-2222-2222-222222222222",
            data: {
               code: "print('hello')",
               language: "python",
               title: "Regression Example",
               outputs: [],
               showCode: true
            },
            config: {
               instanceId: "33333333-3333-3333-3333-333333333333"
            },
            onChange: jest.fn()
         })
      );

      const headerLeft = container.querySelector(".code-block__header-left");
      const titleInput = container.querySelector(".code-block__title-input");
      const languageLabel = container.querySelector(
         ".code-block__language-label"
      );
      const separator = container.querySelector(".code-block__title-separator");

      expect(headerLeft?.contains(titleInput ?? null)).toBe(true);
      expect(languageLabel?.textContent).toBe("Python");
      expect(separator?.textContent).toBe("/");
      expect(screen.getByDisplayValue("Regression Example")).toBeTruthy();
   });

   it("shows only Python when the title is empty", () => {
      const { container } = render(
         React.createElement(CodeBlockComponent, {
            id: "22222222-2222-2222-2222-222222222222",
            data: {
               code: "print('hello')",
               language: "javascript",
               title: "",
               outputs: [],
               showCode: true
            },
            config: {
               instanceId: "33333333-3333-3333-3333-333333333333"
            },
            onChange: jest.fn(),
            readonly: true
         })
      );

      const languageLabel = container.querySelector(
         ".code-block__language-label"
      );
      const separator = container.querySelector(".code-block__title-separator");

      expect(languageLabel?.textContent).toBe("Python");
      expect(separator).toBeNull();
      expect(
         (screen.getByLabelText("Code block title") as HTMLInputElement).value
      ).toBe("");
   });
});

describe("CodeBlockOutputs text output", () => {
   it("preserves newline characters in text output", () => {
      render(
         React.createElement(CodeBlockOutputs, {
            outputs: [
               {
                  type: "text",
                  mimeType: "text/plain",
                  content: "alpha\nbeta"
               }
            ]
         })
      );

      // Newlines must survive rendering: the browser default collapses line
      // breaks into spaces, so the output element has to be pre-wrap.
      expect(screen.getByText(/alpha\s+beta/).style.whiteSpace).toBe(
         "pre-wrap"
      );
   });
});
