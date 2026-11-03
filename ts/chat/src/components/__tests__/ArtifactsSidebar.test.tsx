/// <reference types="jest" />

import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { ArtifactType, type ChatSessionModel } from "@kontext-labs/schema";
import ArtifactsSidebar from "../ArtifactsSidebar";
import { useChatSessionStore } from "../../stores/chatSessionStore";

jest.mock("../../stores/chatSessionStore", () => {
   const { create } = jest.requireActual<typeof import("zustand")>("zustand");

   const useChatSessionStore = create<{
      activeArtifactId: string | null;
      chatSession: ChatSessionModel | null;
      setActiveArtifact: (artifactId: string | null) => void;
      reset: () => void;
   }>((set) => ({
      activeArtifactId: null,
      chatSession: null,
      setActiveArtifact: (activeArtifactId) => set({ activeArtifactId }),
      reset: () =>
         set({
            activeArtifactId: null,
            chatSession: null
         })
   }));

   return { useChatSessionStore };
});

jest.mock("@kontext-labs/icons", () => {
   const React = jest.requireActual<typeof import("react")>("react");

   const Icon = ({ name }: { name: string }) =>
      React.createElement("span", { "data-testid": name }, name);

   return {
      CloseOutlined: () => React.createElement(Icon, { name: "close-icon" }),
      PanelLeftCloseOutlined: () =>
         React.createElement(Icon, { name: "panel-close-icon" }),
      FileChartLineOutlined: () =>
         React.createElement(Icon, { name: "chart-icon" }),
      FileImageOutlined: () =>
         React.createElement(Icon, { name: "image-icon" }),
      FileTextOutlined: () => React.createElement(Icon, { name: "file-icon" }),
      NotebookOutlined: () =>
         React.createElement(Icon, { name: "notebook-icon" }),
      TableOutlined: () => React.createElement(Icon, { name: "table-icon" })
   };
});

jest.mock("antd", () => {
   const React = jest.requireActual<typeof import("react")>("react");

   const Button = ({
      children,
      onClick,
      icon,
      title,
      ...props
   }: React.ButtonHTMLAttributes<HTMLButtonElement> & {
      icon?: React.ReactNode;
   }) =>
      React.createElement(
         "button",
         {
            "type": "button",
            onClick,
            "aria-label": title || (children ? undefined : "icon-button"),
            title,
            ...props
         },
         icon,
         children
      );

   const Card = ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", null, children);

   const Flex = ({ children }: { children: React.ReactNode }) =>
      React.createElement("div", null, children);

   const Tabs = ({
      items,
      activeKey,
      onChange
   }: {
      items: Array<{
         key: string;
         label: React.ReactNode;
         children: React.ReactNode;
      }>;
      activeKey?: string;
      onChange?: (key: string) => void;
   }) => {
      const current =
         items.find((item) => item.key === activeKey) ?? items[0] ?? null;

      return React.createElement(
         "div",
         null,
         React.createElement(
            "div",
            null,
            items.map((item) =>
               React.createElement(
                  "div",
                  { key: item.key },
                  React.createElement(
                     "button",
                     {
                        "type": "button",
                        "data-testid": `tab-trigger-${item.key}`,
                        "onClick": () => onChange?.(item.key)
                     },
                     `Open ${item.key}`
                  ),
                  item.label
               )
            )
         ),
         React.createElement(
            "div",
            { "data-testid": "active-tab-panel" },
            current?.children
         )
      );
   };

   return {
      Button,
      Card,
      Flex,
      Tabs,
      theme: {
         useToken: () => ({
            token: {
               colorTextSecondary: "#666",
               colorFillSecondary: "#f5f5f5",
               colorFillTertiary: "#fafafa",
               colorBorderSecondary: "#d9d9d9"
            }
         })
      },
      Typography: {
         Text: ({ children }: { children: React.ReactNode }) =>
            React.createElement("span", null, children)
      }
   };
});

const makeArtifact = (
   artifactId: string,
   artifactType: ArtifactType,
   title: string
) => ({
   id: artifactId,
   sessionId: "11111111-1111-1111-1111-111111111111",
   artifactId,
   artifactType,
   title,
   meta: {},
   createdAt: "2026-01-01T00:00:00Z",
   updatedAt: "2026-01-01T00:00:00Z"
});

describe("ArtifactsSidebar", () => {
   beforeEach(() => {
      useChatSessionStore.getState().reset();
   });

   it("renders the empty state when there are no artifacts", () => {
      render(
         <ArtifactsSidebar
            artifacts={[]}
            renderArtifactContent={() => <div>unused</div>}
         />
      );

      expect(screen.getByText(/No artifacts yet/i)).toBeInTheDocument();
   });

   it("initializes and switches the active artifact through the shared store", async () => {
      const artifacts = [
         makeArtifact("artifact-1", ArtifactType.Notebook, "Notebook"),
         makeArtifact("artifact-2", ArtifactType.Chart, "Chart")
      ];

      render(
         <ArtifactsSidebar
            artifacts={artifacts}
            renderArtifactContent={({ artifact }) => (
               <div>{`content-${artifact.artifactId}`}</div>
            )}
         />
      );

      await waitFor(() => {
         expect(useChatSessionStore.getState().activeArtifactId).toBe(
            "artifact-1"
         );
      });

      expect(screen.getByText("content-artifact-1")).toBeInTheDocument();

      fireEvent.click(screen.getByTestId("tab-trigger-artifact-2"));

      expect(useChatSessionStore.getState().activeArtifactId).toBe(
         "artifact-2"
      );
      expect(screen.getByText("content-artifact-2")).toBeInTheDocument();
   });

   it("updates the first tab title and auto-renames the session only once", async () => {
      const onAutoRename = jest.fn();

      useChatSessionStore.setState({
         chatSession: {
            id: "session-1",
            sessionName: "Chat - Untitled"
         } as ChatSessionModel
      });

      render(
         <ArtifactsSidebar
            artifacts={[
               makeArtifact("artifact-1", ArtifactType.Notebook, "Notebook")
            ]}
            onAutoRename={onAutoRename}
            renderArtifactContent={({ onTitleChange }) => (
               <button
                  type="button"
                  onClick={() => onTitleChange("Renamed Notebook")}
               >
                  Rename
               </button>
            )}
         />
      );

      fireEvent.click(screen.getByRole("button", { name: "Rename" }));

      await waitFor(() => {
         expect(onAutoRename).toHaveBeenCalledWith("Renamed Notebook");
      });

      expect(screen.getByText("Renamed Notebook")).toBeInTheDocument();

      fireEvent.click(screen.getByRole("button", { name: "Rename" }));

      await waitFor(() => {
         expect(onAutoRename).toHaveBeenCalledTimes(1);
      });
   });

   it("calls onRemoveArtifact for the matching tab", () => {
      const onRemoveArtifact = jest.fn();

      render(
         <ArtifactsSidebar
            artifacts={[
               makeArtifact("artifact-1", ArtifactType.Notebook, "Notebook")
            ]}
            onRemoveArtifact={onRemoveArtifact}
            renderArtifactContent={() => <div>content</div>}
         />
      );

      fireEvent.click(screen.getByRole("button", { name: "icon-button" }));

      expect(onRemoveArtifact).toHaveBeenCalledWith("artifact-1");
   });
});
