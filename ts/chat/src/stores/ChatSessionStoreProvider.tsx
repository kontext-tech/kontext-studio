import type { ApiErrorResult } from "@kontext-labs/common";
import { useUserStore } from "@kontext-labs/identity";
import type { ProjectModel } from "@kontext-labs/schema";
import React, { useEffect, useMemo } from "react";
import {
   ChatSessionStoreContext,
   createChatSessionStore
} from "./chatSessionStore";

export interface ChatSessionStoreProviderProps {
   /**
    * The project the chat UI belongs to. A fresh store instance is created per
    * project id; while the project is still loading, consumers must not read
    * the store (the guard components never mount them before the project
    * resolves).
    */
   project?: ProjectModel | null;
   /** API error handler shared with the configured chat service. */
   errorHandler?: (error: ApiErrorResult) => Promise<void>;
   children?: React.ReactNode;
}

/**
 * Provides one chat session store per project.
 *
 * Mount once per project scope (the app mounts it in `ProjectLayout`,
 * covering both the side menu and all project routes). The provider owns
 * service initialization: `chatService` is created/refreshed here so pages
 * never duplicate the "initialize + reset" effect.
 *
 * Because the store instance is per project, project switches get a new store
 * with clean state — there is no global "reset on project change" step.
 */
export const ChatSessionStoreProvider = ({
   project,
   errorHandler,
   children
}: ChatSessionStoreProviderProps) => {
   const projectId = project?.id;
   const store = useMemo(
      () => (projectId ? createChatSessionStore() : null),
      [projectId]
   );

   const accessToken = useUserStore((state) => state.tokens?.accessToken);

   useEffect(() => {
      if (!store || !projectId || !accessToken || !project) {
         return;
      }

      store
         .getState()
         .initializeChatService(project, { accessToken }, errorHandler);
   }, [store, projectId, accessToken, project, errorHandler]);

   return (
      <ChatSessionStoreContext.Provider value={store}>
         {children}
      </ChatSessionStoreContext.Provider>
   );
};
