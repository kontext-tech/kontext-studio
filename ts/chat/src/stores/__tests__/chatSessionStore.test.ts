/// <reference types="jest" />

jest.mock("../../ChatService", () => ({
   ChatService: class ChatService {}
}));

import type { ChatSessionService } from "../../types/chatSessionService";
import { createChatSessionStore } from "../chatSessionStore";

const chatSessionStore = createChatSessionStore();

describe("chatSessionStore artifact event flow", () => {
   beforeEach(() => {
      chatSessionStore.getState().reset();
      chatSessionStore.setState({
         projectId: "project-1",
         chatSession: {
            id: "session-1",
            projectId: "project-1",
            sessionName: "Session",
            ownerId: null,
            dateCreated: "2026-05-08T00:00:00Z",
            pythonExecutionApprovalMode: "always_ask",
            isDeleted: false
         }
      });
   });

   it("does not infer artifacts from ToolCallCompleted results", async () => {
      const chatService: Partial<ChatSessionService> = {
         chatStream: async (_projectId, _sessionId, _message, options) => {
            await options.onEvent?.({
               eventType: "ToolCallCompleted",
               eventData: {
                  tool: {
                     toolCallId: "tool-1",
                     toolName: "create_notebook",
                     result: {
                        type: "notebook_mutation",
                        success: true,
                        message: "created",
                        notebookId: "artifact-1",
                        actions: [
                           {
                              actionType: "updateMetadata",
                              sequence: 1,
                              payload: {
                                 varField: "title",
                                 value: "Notebook"
                              }
                           }
                        ]
                     }
                  }
               }
            });
            await options.onEvent?.({
               eventType: "RunCompleted"
            });
            options.onComplete?.();
            return {
               succeed: true,
               data: undefined
            };
         }
      };

      chatSessionStore
         .getState()
         .setChatService(chatService as ChatSessionService);

      await chatSessionStore.getState().sendMessage("hello");

      const state = chatSessionStore.getState();
      expect(state.artifacts).toHaveLength(0);
      expect(state.artifactRuntimeById).toEqual({});
   });

   it("applies artifact updates only from ArtifactEvent", async () => {
      const chatService: Partial<ChatSessionService> = {
         chatStream: async (_projectId, _sessionId, _message, options) => {
            await options.onEvent?.({
               eventType: "ToolCallCompleted",
               eventData: {
                  tool: {
                     toolCallId: "tool-1",
                     toolName: "create_notebook",
                     result: {
                        type: "notebook_mutation",
                        success: true,
                        message: "created",
                        notebookId: "artifact-1",
                        actions: [
                           {
                              actionType: "updateMetadata",
                              sequence: 1,
                              payload: {
                                 varField: "title",
                                 value: "Notebook"
                              }
                           }
                        ]
                     }
                  }
               }
            });
            await options.onEvent?.({
               eventType: "ArtifactEvent",
               eventData: {
                  kind: "created",
                  artifact: {
                     id: "record-1",
                     sessionId: "session-1",
                     artifactId: "artifact-1",
                     artifactType: "Notebook",
                     title: "Notebook",
                     createdAt: "2026-05-08T00:00:00Z",
                     updatedAt: "2026-05-08T00:00:00Z",
                     meta: null
                  },
                  actions: [
                     {
                        actionType: "updateMetadata",
                        sequence: 1,
                        payload: {
                           varField: "title",
                           value: "Notebook"
                        }
                     }
                  ],
                  sourceToolCallId: "tool-1"
               }
            });
            await options.onEvent?.({
               eventType: "RunCompleted"
            });
            options.onComplete?.();
            return {
               succeed: true,
               data: undefined
            };
         }
      };

      chatSessionStore
         .getState()
         .setChatService(chatService as ChatSessionService);

      await chatSessionStore.getState().sendMessage("hello");

      const state = chatSessionStore.getState();
      expect(state.artifacts).toHaveLength(1);
      expect(
         state.artifactRuntimeById["artifact-1"]?.pendingActions
      ).toHaveLength(1);
   });
});
