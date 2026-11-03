import { routeRegistry } from "@/routing";
import { RouteNames, type RouteConfig, type RoutingContextInfo } from "@/types";
import type { ProjectModel, ProjectNavModel } from "@kontext-labs/schema";
import { createRouteHook } from "@kontext-labs/app-runtime/router";
import { useCallback } from "react";
import { useParams } from "react-router-dom";

const useRouteCore = createRouteHook<
   RouteNames,
   RouteConfig,
   RoutingContextInfo
>(routeRegistry);
/**
 * Custom hook that provides information about the current route
 *
 * @returns An object with route information and utility functions
 */
export const useRoute = () => {
   const params = useParams();
   const {
      currentPath,
      queryParams,
      getQueryParam,
      currentRoute,
      getResolvedRouteConfig,
      getResolvedRoutePath,
      getResolvedRouteKey
   } = useRouteCore();

   const getRouteInstance = useCallback(
      (
         routeName: RouteNames,
         project?: ProjectNavModel | ProjectModel | null,
         additionalInfo?: Record<string, string>
      ) => {
         return getResolvedRouteConfig(routeName, {
            project: project ?? undefined,
            additionalInfo
         });
      },
      [getResolvedRouteConfig]
   );

   const getRouteInstanceKey = useCallback(
      (
         routeConfig: RouteConfig,
         project?: ProjectNavModel | ProjectModel | null
      ) => {
         return getResolvedRouteKey(routeConfig, {
            project: project ?? undefined
         });
      },
      [getResolvedRouteKey]
   );

   const getRoutePath = useCallback(
      (
         routeName: RouteNames,
         project?: ProjectNavModel | ProjectModel | null,
         additionalInfo?: Record<string, string>
      ) =>
         getResolvedRoutePath(routeName, {
            project: project ?? undefined,
            additionalInfo
         }),
      [getResolvedRoutePath]
   );

   const getGeneralRoutePath = useCallback(
      (routeName: RouteNames) => getResolvedRoutePath(routeName),
      [getResolvedRoutePath]
   );

   // File-specific routing helpers
   const getFileDetailPath = useCallback(
      (
         project: ProjectNavModel | ProjectModel | null,
         fileId: string,
         fileName?: string
      ) => {
         if (!project) {
            throw new Error("Project is required for file routes");
         }

         const additionalInfo = {
            fileId,
            ...(fileName && { fileName })
         };

         return getRoutePath(
            RouteNames.PROJECT_FILE_DETAIL,
            project,
            additionalInfo
         );
      },
      [getRoutePath]
   );

   const getFilesOverviewPath = useCallback(
      (project: ProjectNavModel | ProjectModel | null) => {
         return getRoutePath(RouteNames.PROJECT_FILES, project);
      },
      [getRoutePath]
   );

   // Project-specific routing helpers
   const getProjectHomePath = useCallback(
      (project?: ProjectNavModel | ProjectModel | null) => {
         return getRoutePath(RouteNames.PROJECT, project);
      },
      [getRoutePath]
   );

   const getProjectSettingsPath = useCallback(
      (project?: ProjectNavModel | ProjectModel | null) => {
         return getRoutePath(RouteNames.PROJECT_SETTINGS, project);
      },
      [getRoutePath]
   );

   const getProjectCatalogsPath = useCallback(
      (project?: ProjectNavModel | ProjectModel | null) => {
         return getRoutePath(RouteNames.PROJECT_CATALOGS, project);
      },
      [getRoutePath]
   );

   const getProjectJobsPath = useCallback(
      (project?: ProjectNavModel | ProjectModel | null) => {
         return getRoutePath(RouteNames.PROJECT_JOBS, project);
      },
      [getRoutePath]
   );

   // Chat-specific routing helpers
   const getProjectChatPath = useCallback(
      (project: ProjectNavModel | ProjectModel | null) => {
         return getRoutePath(RouteNames.PROJECT, project);
      },
      [getRoutePath]
   );

   const getProjectChatSessionsPath = useCallback(
      (project: ProjectNavModel | ProjectModel | null) => {
         return getRoutePath(RouteNames.PROJECT_CHAT_SESSIONS, project);
      },
      [getRoutePath]
   );

   const getProjectChatSessionDetailPath = useCallback(
      (
         project: ProjectNavModel | ProjectModel | null,
         sessionId: string,
         sessionName?: string
      ) => {
         const additionalInfo = {
            sessionId,
            sessionName: sessionName || "Chat Session"
         };
         return getRoutePath(
            RouteNames.PROJECT_CHAT_SESSION_DETAIL,
            project,
            additionalInfo
         );
      },
      [getRoutePath]
   );

   // Knowledge-specific routing helpers
   const getKnowledgePath = useCallback(
      (project?: ProjectNavModel | ProjectModel | null) =>
         getRoutePath(RouteNames.PROJECT_KNOWLEDGE, project),
      [getRoutePath]
   );

   const getKnowledgeDetailPath = useCallback(
      (project: ProjectNavModel | ProjectModel | null, conceptId: string) =>
         getRoutePath(RouteNames.PROJECT_KNOWLEDGE_DETAIL, project, {
            conceptId
         }),
      [getRoutePath]
   );

   // Notebook-specific routing helpers
   const getNotebookDetailPath = useCallback(
      (project: ProjectNavModel | ProjectModel | null, notebookId: string) => {
         const additionalInfo = {
            fileId: notebookId
         };

         return getRoutePath(
            RouteNames.PROJECT_NOTEBOOK_DETAIL,
            project,
            additionalInfo
         );
      },
      [getRoutePath]
   );

   return {
      currentPath,
      params,
      queryParams,
      getQueryParam,
      currentRoute,
      getRouteInstance,
      getRoutePath,
      getGeneralRoutePath,
      getRouteInstanceKey,
      // File-specific helpers
      getFileDetailPath,
      getFilesOverviewPath,
      // Project-specific helpers
      getProjectHomePath,
      getProjectCatalogsPath,
      getProjectJobsPath,
      getProjectSettingsPath,
      getKnowledgePath,
      getKnowledgeDetailPath,
      getProjectChatPath,
      getProjectChatSessionsPath,
      getProjectChatSessionDetailPath,
      getNotebookDetailPath
   };
};
