import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { usePythonEnvironment } from "@/hooks/usePythonEnvironment";
import { useDataService, useService } from "@kontext-labs/app-runtime/hooks";
import { ChatService, ModelProviderService } from "@kontext-labs/chat";
import {
   SiteFeature,
   type ChatSessionModel,
   type ModelConnection,
   type ProjectModel
} from "@kontext-labs/schema";
import { useSiteConfigStore } from "@kontext-labs/site";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

export type ReadinessState = "loading" | "ready" | "missing" | "unknown";

export interface RecentChat {
   session: ChatSessionModel;
   project: ProjectModel;
}

export interface ReadinessItem {
   key: "model" | "python";
   state: ReadinessState;
   title: string;
   detail: string;
}

const sessionTimestamp = (session: ChatSessionModel) =>
   new Date(session.dateModified ?? session.dateCreated).getTime();

const projectTimestamp = (project: ProjectModel) =>
   new Date(project.dateModified ?? project.dateCreated ?? 0).getTime();

/**
 * Recent chats across the user's most recently touched projects. The API is
 * project-scoped, so this fans out over the top projects and keeps the newest
 * sessions; a failing project is skipped rather than failing the whole block.
 */
export function useRecentChats(projects: ProjectModel[], limit = 4) {
   const apiErrorHandler = useApiErrorHandler();
   const chatService = useDataService(ChatService, apiErrorHandler);

   const recentProjects = useMemo(
      () =>
         [...projects]
            .sort((a, b) => projectTimestamp(b) - projectTimestamp(a))
            .slice(0, 3),
      [projects]
   );

   const projectKey = recentProjects.map((project) => project.id).join("|");

   const query = useQuery<RecentChat[]>({
      queryKey: ["home", "recent-chats", projectKey],
      enabled: recentProjects.length > 0,
      staleTime: 30_000,
      queryFn: async () => {
         const results = await Promise.all(
            recentProjects.map(async (project) => {
               const response = await chatService.getFilteredChatSessions(
                  project.id,
                  undefined,
                  1,
                  3,
                  true
               );

               if (!response.succeed || !response.data) {
                  return [];
               }

               return response.data.items.map((session) => ({
                  session,
                  project
               }));
            })
         );

         return results
            .flat()
            .sort(
               (a, b) =>
                  sessionTimestamp(b.session) - sessionTimestamp(a.session)
            )
            .slice(0, limit);
      }
   });

   return {
      recentChats: query.data ?? [],
      isLoading: query.isLoading
   };
}

/**
 * Setup state for the local workspace. Only checks the pieces the running
 * profile exposes; anything unavailable in this deployment is omitted.
 */
export function useWorkspaceReadiness() {
   const apiErrorHandler = useApiErrorHandler();
   const siteConfig = useSiteConfigStore((state) => state.siteConfig);
   const features = siteConfig?.features ?? [];

   const hasModelConnections = features.includes(SiteFeature.MODEL_CONNECTIONS);
   const hasPythonEnvironment = features.includes(
      SiteFeature.PYTHON_ENVIRONMENT
   );

   const modelProviderService = useService(
      ModelProviderService,
      apiErrorHandler
   );

   const modelsQuery = useQuery<ModelConnection[]>({
      queryKey: ["home", "model-connections"],
      enabled: hasModelConnections,
      staleTime: 30_000,
      queryFn: async () => {
         const response = await modelProviderService.getModelProviders();
         if (!response.succeed || !response.data) {
            throw new Error("Failed to load model providers");
         }
         return response.data;
      }
   });

   const python = usePythonEnvironment({ enabled: hasPythonEnvironment });

   const model: ReadinessItem | null = hasModelConnections
      ? (() => {
           if (modelsQuery.isLoading) {
              return {
                 key: "model",
                 state: "loading",
                 title: "Model provider",
                 detail: "Checking connections..."
              };
           }

           if (modelsQuery.isError) {
              return {
                 key: "model",
                 state: "unknown",
                 title: "Model provider",
                 detail: "Status unavailable"
              };
           }

           const enabled = (modelsQuery.data ?? []).filter(
              (connection) => connection.enabled !== false
           );
           const preferred =
              enabled.find((connection) => connection.isDefault) ?? enabled[0];

           return {
              key: "model",
              state: preferred ? "ready" : "missing",
              title: "Model provider",
              detail: preferred
                 ? preferred.displayName
                 : "Connect a model to start chatting"
           };
        })()
      : null;

   const pythonItem: ReadinessItem | null = hasPythonEnvironment
      ? (() => {
           if (python.isLoading) {
              return {
                 key: "python",
                 state: "loading",
                 title: "Python runtime",
                 detail: "Checking environment..."
              };
           }

           if (python.errorMessage || !python.environment) {
              return {
                 key: "python",
                 state: "unknown",
                 title: "Python runtime",
                 detail: "Status unavailable"
              };
           }

           const ready =
              python.environment.available && python.environment.initialized;

           return {
              key: "python",
              state: ready ? "ready" : "missing",
              title: "Python runtime",
              detail: ready
                 ? `Python ${python.environment.pythonVersion}`
                 : "Not prepared yet — required for Python blocks"
           };
        })()
      : null;

   const items = [model, pythonItem].filter(
      (item): item is ReadinessItem => item !== null
   );

   return {
      items,
      needsSetup: items.some((item) => item.state === "missing"),
      modelLabel: model?.state === "ready" ? model.detail : undefined,
      pythonLabel: pythonItem?.state === "ready" ? pythonItem.detail : undefined
   };
}
