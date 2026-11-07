/** @jest-environment jsdom */

import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { SqlBlockComponent, SqlBlockPreview } from "./SqlBlockComponent";

const mockUpdateSqlBlock = jest.fn();
const mockUpdateSqlBlockRuntime = jest.fn();
const mockExecuteQuery = jest.fn();
const mockOnViewExecutionRun = jest.fn();
const mockOnChange = jest.fn();
const mockStoreBlocks: Array<{
   id: string;
   type: string;
   data?: { alias?: string | null };
}> = [];

jest.mock("@kontext-tech/icons", () => {
   const React = jest.requireActual<typeof import("react")>("react");

   const Icon = ({ name }: { name: string }) =>
      React.createElement("span", { "data-testid": name }, name);

   return {
      CodeOutlined: () => React.createElement(Icon, { name: "code" }),
      CopyOutlined: () => React.createElement(Icon, { name: "copy" }),
      DatabaseOutlined: () => React.createElement(Icon, { name: "database" }),
      DownOutlined: () => React.createElement(Icon, { name: "down" }),
      EyeOutlined: () => React.createElement(Icon, { name: "eye" }),
      InfoCircleOutlined: () => React.createElement(Icon, { name: "info" }),
      LoadingOutlined: () => React.createElement(Icon, { name: "loading" }),
      PlayCircleOutlined: () => React.createElement(Icon, { name: "play" }),
      UpOutlined: () => React.createElement(Icon, { name: "up" })
   };
});

jest.mock("@kontext-tech/ui", () => ({
   LoadingSpinner: () => null
}));

jest.mock("@kontext-tech/query/query-results", () => ({
   __esModule: true,
   default: () => null
}));

jest.mock("@kontext-tech/query/sql-editor", () => ({
   __esModule: true,
   default: () => null
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
      React.createElement("input", { ...props, value, onChange });

   const Drawer = ({
      open,
      children,
      title
   }: {
      open?: boolean;
      children?: React.ReactNode;
      title?: React.ReactNode;
   }) =>
      open
         ? React.createElement(
              "div",
              { "data-testid": "sql-editor-drawer" },
              title,
              children
           )
         : null;

   const Splitter = ({ children }: { children?: React.ReactNode }) =>
      React.createElement("div", null, children);
   Splitter.Panel = ({ children }: { children?: React.ReactNode }) =>
      React.createElement("div", null, children);

   const Popover = ({
      children,
      content,
      title
   }: {
      children?: React.ReactNode;
      content?: React.ReactNode;
      title?: React.ReactNode;
   }) =>
      React.createElement(
         "span",
         null,
         children,
         content
            ? React.createElement(
                 "div",
                 { "data-testid": "sql-alias-popover" },
                 title,
                 content
              )
            : null
      );

   const Space = Object.assign(
      ({ children }: { children?: React.ReactNode }) =>
         React.createElement("div", null, children),
      {
         Compact: ({ children }: { children?: React.ReactNode }) =>
            React.createElement("div", null, children)
      }
   );

   return {
      Alert: ({ children }: { children?: React.ReactNode }) =>
         React.createElement("div", null, children),
      Button,
      Drawer,
      Input,
      Popover,
      Space,
      Splitter,
      Tabs: ({ items }: { items?: Array<{ children?: React.ReactNode }> }) =>
         React.createElement(
            "div",
            null,
            (items ?? []).map((item) => item.children)
         ),
      Tag: ({ children }: { children?: React.ReactNode }) =>
         React.createElement("span", null, children),
      Tooltip: ({ children }: { children?: React.ReactNode }) =>
         React.createElement(React.Fragment, null, children),
      Typography: {
         Text: ({ children }: { children?: React.ReactNode }) =>
            React.createElement("span", null, children)
      },
      theme: {
         useToken: () => ({
            token: {
               colorFillAlter: "#f5f5f5",
               colorBgContainer: "#fff",
               colorBorder: "#ddd",
               colorBorderSecondary: "#ddd",
               colorTextSecondary: "#222",
               colorTextQuaternary: "#999",
               marginSM: 8,
               padding: 16,
               paddingSM: 12,
               paddingMD: 16
            }
         })
      }
   };
});

jest.mock("@notebook/context/NotebookServiceContext", () => ({
   useNotebookServices: () => ({
      projectId: "project-1",
      notebookId: "11111111-1111-1111-1111-111111111111",
      onViewExecutionRun: mockOnViewExecutionRun
   })
}));

jest.mock("@notebook/hooks/useExecuteCell", () => ({
   useExecuteCell: () => ({ execute: mockExecuteQuery })
}));

jest.mock("@notebook/hooks/useTheme", () => ({
   useTheme: () => ({ isDarkMode: false, themeConfig: {} })
}));

jest.mock("@notebook/hooks/useInlineData", () => ({
   invalidateNotebookDataCache: jest.fn(),
   useNotebookInlineData: () => ({
      data: undefined,
      isLoading: false,
      error: null
   })
}));

jest.mock("@notebook/stores/notebookStore", () => {
   const useNotebookStore = Object.assign(
      jest.fn(
         (selector: (state: { getSqlBlock: () => undefined }) => unknown) =>
            selector({ getSqlBlock: () => undefined })
      ),
      {
         getState: () => ({
            updateSqlBlockRuntime: mockUpdateSqlBlockRuntime,
            updateSqlBlock: mockUpdateSqlBlock,
            instances: {
               "default": { document: { blocks: mockStoreBlocks } },
               "notebook-1": { document: { blocks: mockStoreBlocks } }
            }
         })
      }
   );

   return { useNotebookStore };
});

describe("SqlBlockComponent full editor drawer", () => {
   beforeEach(() => {
      mockUpdateSqlBlock.mockReset();
      mockUpdateSqlBlockRuntime.mockReset();
      mockExecuteQuery.mockReset();
      mockOnViewExecutionRun.mockReset();
   });

   it("opens the editor for a block that is not yet saved to the store", () => {
      render(
         React.createElement(SqlBlockComponent, {
            id: "block-1",
            data: { title: "SQL Query", code: "SELECT 1" },
            config: { instanceId: "notebook-1", projectId: "project-1" },
            onChange: jest.fn()
         })
      );

      expect(screen.queryByTestId("sql-editor-drawer")).toBeNull();

      fireEvent.click(screen.getByTestId("code").closest("button")!);

      expect(screen.getByTestId("sql-editor-drawer")).toBeTruthy();
      expect(mockUpdateSqlBlockRuntime).toHaveBeenCalledWith(
         "block-1",
         { isEditorOpen: true },
         "notebook-1"
      );
   });
});

describe("SqlBlockComponent execution run link", () => {
   beforeEach(() => {
      mockUpdateSqlBlock.mockReset();
      mockUpdateSqlBlockRuntime.mockReset();
      mockExecuteQuery.mockReset();
      mockOnViewExecutionRun.mockReset();
   });

   it("persists the execution run id with the results on query execution", async () => {
      mockExecuteQuery.mockResolvedValue({
         status: "success",
         executionRunId: "run-456",
         output: {
            dataRef: { dataId: "data-1" }
         }
      });

      const onChange = jest.fn();

      render(
         React.createElement(SqlBlockComponent, {
            id: "block-1",
            data: { title: "SQL Query", code: "SELECT 1" },
            config: { instanceId: "notebook-1", projectId: "project-1" },
            onChange
         })
      );

      // Run button (tooltip-wrapped play icon).
      fireEvent.click(screen.getByTestId("play").closest("button")!);

      await waitFor(() => {
         expect(mockExecuteQuery).toHaveBeenCalledTimes(1);
      });

      // Run id persisted with the results reference in the store...
      expect(mockUpdateSqlBlock).toHaveBeenCalledWith(
         "block-1",
         expect.objectContaining({
            dataRef: { dataId: "data-1" },
            executionRunId: "run-456"
         }),
         "notebook-1"
      );
      // ...and in the notebook document.
      expect(onChange).toHaveBeenCalledWith(
         expect.objectContaining({ executionRunId: "run-456" })
      );
   });

   it("opens the job run drawer from the editor drawer, not the card header", async () => {
      render(
         React.createElement(SqlBlockComponent, {
            id: "block-1",
            data: {
               title: "SQL Query",
               code: "SELECT 1",
               executionRunId: "run-456"
            },
            config: { instanceId: "notebook-1", projectId: "project-1" },
            onChange: jest.fn()
         })
      );

      // The block card header stays link-free.
      expect(screen.queryByText("Run details")).toBeNull();

      // Open the full editor drawer; its header row exposes the run.
      fireEvent.click(screen.getByTestId("code").closest("button")!);

      fireEvent.click(await screen.findByText("Run details"));
      expect(mockOnViewExecutionRun).toHaveBeenCalledWith("run-456");
   });

   it("opens the job run drawer from the readonly preview header", () => {
      render(
         React.createElement(SqlBlockPreview, {
            data: {
               title: "SQL Query",
               code: "SELECT 1",
               executionRunId: "run-456"
            }
         })
      );

      fireEvent.click(screen.getByText("Run details"));
      expect(mockOnViewExecutionRun).toHaveBeenCalledWith("run-456");
   });
});

describe("SqlBlockComponent alias", () => {
   beforeEach(() => {
      mockUpdateSqlBlock.mockReset();
      mockUpdateSqlBlockRuntime.mockReset();
      mockExecuteQuery.mockReset();
      mockOnViewExecutionRun.mockReset();
      mockOnChange.mockReset();
      mockStoreBlocks.length = 0;
   });

   const renderBlock = (data: {
      title?: string;
      code?: string;
      alias?: string;
   }) =>
      render(
         React.createElement(SqlBlockComponent, {
            id: "block-1",
            data: { title: "SQL Query", code: "SELECT 1", ...data },
            config: { instanceId: "notebook-1", projectId: "project-1" },
            onChange: mockOnChange
         })
      );

   it("shows the alias chip with a copy affordance once bound", () => {
      renderBlock({ alias: "df_1" });

      // The mocked antd Tag drops testids; assert on the chip label instead.
      expect(screen.getByText("df_1")).toBeTruthy();
      expect(screen.getByLabelText("Copy load_data snippet")).toBeTruthy();
   });

   it("renders no chip before an alias is bound", () => {
      renderBlock({});

      expect(screen.queryByText("df_1")).toBeNull();
   });

   it("keeps an existing alias on re-execution", async () => {
      mockExecuteQuery.mockResolvedValue({
         status: "success",
         executionRunId: "run-1",
         output: { dataRef: { dataId: "data-1" } }
      });
      renderBlock({ alias: "sales_summary" });

      fireEvent.click(screen.getByTestId("play").closest("button")!);

      await waitFor(() => {
         expect(mockUpdateSqlBlock).toHaveBeenCalledTimes(2);
      });
      // The client never *assigns* numbers; it only echoes the server's alias
      // (unset response -> keep the declared one).
      const aliasValues = new Set(
         mockUpdateSqlBlock.mock.calls.map(
            (call) => (call[1] as Record<string, unknown>)["alias"]
         )
      );
      expect(aliasValues).toEqual(new Set(["sales_summary"]));
   });

   it("adopts the server-bound alias from the execution response", async () => {
      mockExecuteQuery.mockResolvedValue({
         status: "success",
         executionRunId: "run-1",
         output: { dataRef: { dataId: "data-1" }, alias: "df_1" }
      });
      renderBlock();

      fireEvent.click(screen.getByTestId("play").closest("button")!);

      await waitFor(() => {
         expect(mockExecuteQuery).toHaveBeenCalledTimes(1);
      });
      expect(mockUpdateSqlBlock).toHaveBeenCalledWith(
         "block-1",
         expect.objectContaining({ alias: "df_1" }),
         "notebook-1"
      );
      expect(mockOnChange).toHaveBeenCalledWith(
         expect.objectContaining({ alias: "df_1" })
      );
   });

   it("rejects a duplicate alias on rename", () => {
      mockStoreBlocks.push({
         id: "block-2",
         type: "sql",
         data: { alias: "taken_name" }
      });
      renderBlock({ alias: "df_1" });

      fireEvent.change(screen.getByTestId("sql-alias-input"), {
         target: { value: "taken_name" }
      });
      fireEvent.click(screen.getByTestId("sql-alias-save"));

      expect(
         screen.getByText(/already used by another SQL block in this notebook/)
      ).toBeTruthy();
   });

   it("rejects an invalid alias name on rename", () => {
      renderBlock({ alias: "df_1" });

      fireEvent.change(screen.getByTestId("sql-alias-input"), {
         target: { value: "9bad-name" }
      });
      fireEvent.click(screen.getByTestId("sql-alias-save"));

      expect(screen.getByText(/letters, numbers and underscores/)).toBeTruthy();
   });
});
