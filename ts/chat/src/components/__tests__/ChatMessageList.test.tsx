/// <reference types="jest" />

import React from "react";
import { render, screen } from "@testing-library/react";
import type { ChatMessage } from "../../types/chat";
import ChatMessageList from "../ChatMessageList";

jest.mock("@ant-design/x", () => {
   const React = jest.requireActual<typeof import("react")>("react");

   return {
      Bubble: {
         List: ({
            items
         }: {
            items: Array<{
               key: string;
               content: React.ReactNode;
               footer?: React.ReactNode;
            }>;
         }) =>
            React.createElement(
               "div",
               null,
               items.map((item) =>
                  React.createElement(
                     "div",
                     { key: item.key },
                     item.content,
                     item.footer
                  )
               )
            )
      }
   };
});

jest.mock("@kontext-tech/identity", () => {
   const React = jest.requireActual<typeof import("react")>("react");

   return {
      useUser: () => ({
         user: {
            id: "user-1"
         }
      }),
      UserAvatar: () => React.createElement("span", null, "user-avatar"),
      UserAvatarById: () =>
         React.createElement("span", null, "user-avatar-by-id")
   };
});

jest.mock("@kontext-tech/ui", () => {
   const React = jest.requireActual<typeof import("react")>("react");

   return {
      RobotAvatar: () => React.createElement("span", null, "robot-avatar"),
      useUiApp: () => ({
         message: {
            success: jest.fn(),
            error: jest.fn()
         }
      })
   };
});

jest.mock("@kontext-tech/icons", () => {
   const React = jest.requireActual<typeof import("react")>("react");

   return {
      CopyOutlined: () => React.createElement("span", null, "copy-icon")
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
      Flex: ({ children }: { children: React.ReactNode }) =>
         React.createElement("div", null, children)
   };
});

jest.mock("../MessageSegmentsDisplay", () => {
   const React = jest.requireActual<typeof import("react")>("react");

   return {
      __esModule: true,
      default: () =>
         React.createElement(
            "div",
            { "data-testid": "message-content" },
            "content"
         )
   };
});

describe("ChatMessageList", () => {
   beforeEach(() => {
      Object.assign(navigator, {
         clipboard: {
            writeText: jest.fn(async () => undefined)
         }
      });
   });

   it("renders custom assistant footer actions beside the copy action", () => {
      const messages = [
         {
            id: "assistant-1",
            type: "assistant",
            status: "completed",
            segments: [
               {
                  segmentType: "text",
                  content: "Plan saved",
                  cid: null,
                  parentId: null
               }
            ]
         }
      ] as ChatMessage[];

      render(
         <ChatMessageList
            messages={messages}
            renderAssistantFooterActions={(_message, context) =>
               context.isLast ? (
                  <button type="button">Implement plan</button>
               ) : null
            }
         />
      );

      expect(
         screen.getByRole("button", { name: "Implement plan" })
      ).toBeInTheDocument();
      expect(screen.getByRole("button", { name: /copy/i })).toBeInTheDocument();
   });
});
