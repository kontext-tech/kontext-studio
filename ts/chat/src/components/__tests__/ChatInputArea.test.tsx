/// <reference types="jest" />

import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ModelCatalogEntry, ProjectModel } from "@kontext-labs/schema";
import ChatInputArea from "../ChatInputArea";

jest.mock("../../useChat", () => ({
   useChat: () => ({
      sendMessage: jest.fn(),
      createChatSession: jest.fn(),
      isLoading: false,
      isMessagesLoading: false,
      isAvailable: true,
      error: null,
      navigateHistory: jest.fn(() => null),
      chatSession: null,
      setPythonExecutionApprovalMode: jest.fn(async () => true),
      setModelSelectionId: jest.fn()
   })
}));

jest.mock("../../stores/chatSessionStore", () => ({
   useChatSessionStore: (
      selector: (state: { modelSelectionId?: string }) => unknown
   ) => selector({ modelSelectionId: undefined })
}));

jest.mock("@kontext-labs/ui", () => ({
   useUiApp: () => ({
      message: {
         error: jest.fn()
      },
      modal: {
         confirm: jest.fn()
      }
   })
}));

jest.mock("@kontext-labs/icons", () => {
   const React = jest.requireActual<typeof import("react")>("react");

   const Icon = ({ name }: { name: string }) =>
      React.createElement("span", { "data-testid": name }, name);

   return {
      CodeOutlined: () => React.createElement(Icon, { name: "code-icon" }),
      RobotOutlined: () => React.createElement(Icon, { name: "robot-icon" })
   };
});

jest.mock("@ant-design/x", () => {
   const React = jest.requireActual<typeof import("react")>("react");

   const Sender = ({
      value,
      onChange,
      onSubmit,
      header,
      footer,
      disabled,
      loading
   }: {
      value: string;
      onChange: (value: string) => void;
      onSubmit: () => void;
      header?: React.ReactNode;
      footer?: (actionNode: React.ReactNode) => React.ReactNode;
      disabled?: boolean;
      loading?: boolean;
   }) => {
      const actionNode = React.createElement(
         "button",
         {
            "type": "button",
            "onClick": onSubmit,
            disabled,
            "data-testid": "sender-submit"
         },
         loading ? "loading" : "send"
      );

      return React.createElement(
         "div",
         null,
         header,
         React.createElement("textarea", {
            value,
            "onChange": (event: React.ChangeEvent<HTMLTextAreaElement>) =>
               onChange(event.target.value),
            "data-testid": "sender-input"
         }),
         footer ? footer(actionNode) : actionNode
      );
   };

   Sender.Header = ({ children }: { children?: React.ReactNode }) =>
      React.createElement("div", null, children);

   return {
      Sender
   };
});

jest.mock("antd", () => {
   const React = jest.requireActual<typeof import("react")>("react");

   const Button = ({
      children,
      onClick,
      disabled,
      icon,
      ...props
   }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
      icon?: React.ReactNode;
   }) =>
      React.createElement(
         "button",
         {
            type: "button",
            onClick,
            disabled,
            ...props
         },
         icon,
         children
      );

   return {
      Button,
      Checkbox: ({ children }: { children: React.ReactNode }) =>
         React.createElement("label", null, children),
      Dropdown: ({ children }: { children: React.ReactNode }) =>
         React.createElement("div", null, children),
      Flex: ({ children }: { children: React.ReactNode }) =>
         React.createElement("div", null, children),
      theme: {
         useToken: () => ({
            token: {
               boxShadowTertiary: "none",
               borderRadiusLG: 8,
               colorTextSecondary: "#666",
               fontSizeSM: 12
            }
         })
      },
      Typography: {
         Text: ({ children }: { children: React.ReactNode }) =>
            React.createElement("span", null, children)
      }
   };
});

const project = {
   id: "11111111-1111-1111-1111-111111111111",
   projectName: "Project",
   projectCode: "PROJECT",
   ownerId: "22222222-2222-2222-2222-222222222222",
   dateCreated: "2026-01-01T00:00:00Z",
   isDeleted: false,
   accessLevel: "Private",
   configuration: {
      allowedFileTypes: [],
      maxFileBytesSize: 1024,
      totalStorageAllocationBytes: 2048,
      features: []
   }
} as unknown as ProjectModel;

const foundationModels = [
   {
      selectionId: "model-1",
      displayName: "Model One",
      connectionKind: "openai"
   }
] as unknown as ModelCatalogEntry[];

describe("ChatInputArea", () => {
   it("renders the pre-session action, status banner, and staged tray", () => {
      render(
         <ChatInputArea
            project={project}
            foundationModels={foundationModels}
            preSessionLeadingAction={<button data-testid="attach-action" />}
            statusBanner={<div data-testid="status-banner">Preparing</div>}
            stagedAttachmentTray={({ hasInput }) => (
               <div data-testid="attachment-tray">
                  {hasInput ? "with-prompt" : "without-prompt"}
               </div>
            )}
            composerHeaderContent={({ hasInput }) => (
               <div data-testid="composer-header">
                  {hasInput ? "header-with-prompt" : "header-without-prompt"}
               </div>
            )}
            composerContent={({ hasInput }) => (
               <div data-testid="composer-content">
                  {hasInput
                     ? "composer-with-prompt"
                     : "composer-without-prompt"}
               </div>
            )}
            onSubmitMessage={jest.fn(async () => undefined)}
         />
      );

      expect(screen.getByTestId("attach-action")).toBeInTheDocument();
      expect(screen.getByTestId("status-banner")).toHaveTextContent(
         "Preparing"
      );
      expect(screen.getByTestId("attachment-tray")).toHaveTextContent(
         "without-prompt"
      );
      expect(screen.getByTestId("composer-header")).toHaveTextContent(
         "header-without-prompt"
      );
      expect(screen.getByTestId("composer-content")).toHaveTextContent(
         "composer-without-prompt"
      );

      fireEvent.change(screen.getByTestId("sender-input"), {
         target: { value: "hello" }
      });

      expect(screen.getByTestId("attachment-tray")).toHaveTextContent(
         "with-prompt"
      );
      expect(screen.getByTestId("composer-header")).toHaveTextContent(
         "header-with-prompt"
      );
      expect(screen.getByTestId("composer-content")).toHaveTextContent(
         "composer-with-prompt"
      );
   });

   it("locks the sender while an external busy state is active", () => {
      render(
         <ChatInputArea
            project={project}
            foundationModels={foundationModels}
            isBusy={true}
            onSubmitMessage={jest.fn(async () => undefined)}
         />
      );

      expect(screen.getByTestId("sender-submit")).toBeDisabled();
      expect(screen.getByTestId("sender-submit")).toHaveTextContent("loading");
   });

   it("uses a custom session settings accessory when provided", async () => {
      render(
         <ChatInputArea
            project={project}
            foundationModels={foundationModels}
            sessionSettingsAccessory={({
               pythonExecutionApprovalMode,
               onPythonExecutionApprovalModeChange
            }) => (
               <button
                  type="button"
                  data-testid="session-settings"
                  onClick={() =>
                     void onPythonExecutionApprovalModeChange("auto_approve")
                  }
               >
                  {pythonExecutionApprovalMode}
               </button>
            )}
            onSubmitMessage={jest.fn(async () => undefined)}
         />
      );

      expect(screen.getByTestId("session-settings")).toHaveTextContent(
         "always_ask"
      );
      expect(screen.queryByText("Ask first")).not.toBeInTheDocument();

      fireEvent.click(screen.getByTestId("session-settings"));

      await waitFor(() => {
         expect(screen.getByTestId("session-settings")).toHaveTextContent(
            "auto_approve"
         );
      });
   });
});
