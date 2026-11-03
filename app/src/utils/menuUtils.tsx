import { getRouteConfig, routeRegistry } from "@/routing";
import { RouteNames, type RoutingContextInfo } from "@/types";
import type { RouteVisibilityContext } from "@/types/routeTypes";
import { createIconFromName } from "@kontext-tech/icons";
import {
   type ChatSessionModel,
   type ProjectModel,
   type SiteConfigResponse
} from "@kontext-tech/schema";
import type { MenuProps } from "antd/es/menu";

// Ant Design Menu types are highly recursive. To avoid "is excessively deep and possibly infinite"
// errors or union narrowing issues during build, we use specific type guards where needed
// or cast to any for event handlers on complex generated items.
export type MenuItem = Required<MenuProps>["items"][number];

/**
 * Result structure for project menu items
 */
export interface ProjectMenuResult {
   topItems: MenuItem[];
   middleItems: MenuItem[];
}

const getMenuItem = (
   routeName: RouteNames,
   context: RoutingContextInfo,
   navigate: (path: string) => void,
   visibilityCtx?: RouteVisibilityContext
): MenuItem => {
   const routeConfig = getRouteConfig(routeName, context);
   const navigationMetadata = routeRegistry.getNavigationMetadata(
      routeName,
      context
   );
   if (!routeConfig) {
      return null;
   }

   // Evaluate visibility predicate if present
   if (navigationMetadata.visible) {
      const ctx: RouteVisibilityContext = visibilityCtx ?? {
         features: []
      };
      if (!navigationMetadata.visible(ctx)) return null;
   }

   const icon =
      typeof navigationMetadata.icon === "string"
         ? createIconFromName(navigationMetadata.icon)
         : navigationMetadata.icon;

   return {
      key: navigationMetadata.key as string,
      label: navigationMetadata.label as string,
      icon,
      onClick: () => navigate(routeConfig.path as string)
   };
};

/**
 * Generates menu items for the project sidebar
 *
 * The sidebar is organised into labelled groups so users can scan by intent
 * rather than reading every entry:
 *  - Pinned top actions: Overview, New Chat
 *  - Workspace: Files, Data Sources, Jobs
 *  - Activity: Query Session History, Activity Log (admin / local mode only)
 *  - Settings: project configuration
 *
 * @param project project data
 * @param navigate Navigation function
 * @param hasRoutePermission Function to check if user has permission for a route
 * @param context Full routing context for robust permission checking
 * @param recentChatSessions Recent chat sessions
 * @param totalChatSessions Total number of chat sessions
 * @param collapsed Whether the sidebar is collapsed
 * @param canViewActivity Whether the user can see audit/monitoring views
 * @returns Structured menu items
 */
export const getProjectMenuItems = (
   project: ProjectModel | null,
   navigate: (path: string) => void,
   hasRoutePermission: (
      routeName: RouteNames,
      context?: RoutingContextInfo
   ) => boolean,
   context?: RoutingContextInfo,
   recentChatSessions: ChatSessionModel[] = [],
   _totalChatSessions: number = 0,
   collapsed: boolean = false,
   canViewActivity: boolean = false
): ProjectMenuResult => {
   if (!project) {
      return { topItems: [], middleItems: [] };
   }

   // Create routing context for the project, merging with provided context
   const routingContext: RoutingContextInfo = {
      project: project,
      ...context
   };

   const topItems: MenuItem[] = [];
   const middleItems: MenuItem[] = [];

   const projectCode = project.projectCode;

   // Workspace-first project navigation:
   // Top: Overview, New Chat
   // Middle: Recent Chats, Files, Data Sources, Jobs, Activity, Settings

   // Helper to build a labelled group from route names, skipping any that are
   // not permitted so feature/role-gated entries never leave an empty group.
   // When the sidebar is collapsed, antd still renders group titles, so we
   // flatten the group into its children to keep only icons visible.
   const buildGroup = (
      keySuffix: string,
      label: string,
      routeNames: RouteNames[]
   ): MenuItem[] => {
      const children = routeNames
         .filter((routeName) => hasRoutePermission(routeName, routingContext))
         .map((routeName) => getMenuItem(routeName, routingContext, navigate))
         .filter((item): item is MenuItem => Boolean(item));

      if (children.length === 0) {
         return [];
      }

      if (collapsed) {
         return children;
      }

      return [
         {
            type: "group",
            key: `project-${projectCode}-${keySuffix}`,
            label,
            children
         } as MenuItem
      ];
   };

   // 1. Route permission checks
   const hasProjectPermission = hasRoutePermission(
      RouteNames.PROJECT_CONSOLE,
      routingContext
   );

   if (hasProjectPermission) {
      const projectConsole = getMenuItem(
         RouteNames.PROJECT_CONSOLE,
         routingContext,
         navigate
      );
      if (projectConsole) {
         topItems.push(projectConsole);
      }
   }

   // 2. New Chat (Top)
   if (hasRoutePermission(RouteNames.PROJECT, routingContext)) {
      const newChat = getMenuItem(RouteNames.PROJECT, routingContext, navigate);
      if (newChat) {
         topItems.push(newChat);
      }
   }

   // 3. Recent Chats (Middle, expanded only)
   if (
      hasRoutePermission(RouteNames.PROJECT_CHAT_SESSIONS, routingContext) &&
      !collapsed
   ) {
      const recentChatItems: MenuItem[] = [];

      recentChatSessions.forEach((session) => {
         recentChatItems.push({
            key: `project-${projectCode}-chat-${session.id}`,
            label: session.sessionName || "Untitled Chat",
            onClick: () => {
               const detailContext: RoutingContextInfo = {
                  ...routingContext,
                  additionalInfo: {
                     sessionId: session.id,
                     sessionName: session.sessionName
                  }
               };
               const detailRoute = getRouteConfig(
                  RouteNames.PROJECT_CHAT_SESSION_DETAIL,
                  detailContext
               );
               if (detailRoute) {
                  navigate(detailRoute.path as string);
               }
            }
         } as MenuItem);
      });

      // Always allow finding all historical chats via "All..." at the bottom of the list
      recentChatItems.push({
         key: `project-${projectCode}-chats-all`,
         label: "All...",
         onClick: () => {
            const chatSessionsRoute = getRouteConfig(
               RouteNames.PROJECT_CHAT_SESSIONS,
               routingContext
            );
            if (chatSessionsRoute) {
               navigate(chatSessionsRoute.path as string);
            }
         }
      } as MenuItem);

      middleItems.push({
         label: "Recent Chats",
         key: `project-${projectCode}-recent-chats`,
         icon: createIconFromName("MessageOutlined"),
         children: recentChatItems
      } as MenuItem);
   }

   // 4. Workspace surfaces (Middle), grouped by intent
   middleItems.push(
      ...buildGroup("group-workspace", "Workspace", [
         RouteNames.PROJECT_FILES,
         RouteNames.PROJECT_CATALOGS,
         RouteNames.PROJECT_KNOWLEDGE,
         RouteNames.PROJECT_JOBS
      ])
   );

   // 5. Activity / audit views (Middle) — only for admins and local mode
   if (canViewActivity) {
      middleItems.push(
         ...buildGroup("group-activity", "Activity", [
            RouteNames.PROJECT_QUERY_SESSIONS,
            RouteNames.PROJECT_EVENTS
         ])
      );
   }

   // 6. Settings (Middle, flat, after the work surfaces)
   if (hasRoutePermission(RouteNames.PROJECT_SETTINGS, routingContext)) {
      const settingsMenuItem = getMenuItem(
         RouteNames.PROJECT_SETTINGS,
         routingContext,
         navigate
      );
      if (settingsMenuItem) {
         middleItems.push(settingsMenuItem);
      }
   }

   return { topItems, middleItems };
};

/**
 * Generates menu items for the user navigation
 *
 * @param navigate Navigation function
 * @param siteConfig Site configuration from the server (determines feature visibility)
 * @returns Array of menu items
 */
export const getUserMenuItems = (
   navigate: (path: string) => void,
   siteConfig?: SiteConfigResponse | null
): MenuItem[] => {
   // Build visibility context from server-advertised features.
   const visibilityCtx: RouteVisibilityContext = {
      features: siteConfig?.features ?? []
   };

   // Build each section independently then join with dividers, so that
   // feature-gated items hidden on this environment don't leave behind
   // orphaned dividers.

   const workspaceItems: MenuItem[] = [];
   const homeMenuItem = getMenuItem(
      RouteNames.HOME,
      {},
      navigate,
      visibilityCtx
   );
   if (homeMenuItem) workspaceItems.push(homeMenuItem);

   const settingsItems: MenuItem[] = [];
   const accountSettingsMenuItem = getMenuItem(
      RouteNames.ACCOUNT_SETTINGS,
      {},
      navigate,
      visibilityCtx
   );
   if (accountSettingsMenuItem) settingsItems.push(accountSettingsMenuItem);

   const modelConnectionsMenuItem = getMenuItem(
      RouteNames.USER_MODEL_CONNECTIONS,
      {},
      navigate,
      visibilityCtx
   );
   if (modelConnectionsMenuItem) settingsItems.push(modelConnectionsMenuItem);

   const pythonEnvironmentMenuItem = getMenuItem(
      RouteNames.USER_PYTHON_ENVIRONMENT,
      {},
      navigate,
      visibilityCtx
   );
   if (pythonEnvironmentMenuItem) settingsItems.push(pythonEnvironmentMenuItem);

   // Join non-empty sections with dividers (no leading/trailing dividers)
   const sections = [workspaceItems, settingsItems].filter(
      (section) => section.length > 0
   );
   return sections.reduce<MenuItem[]>((acc, section, idx) => {
      if (idx > 0) acc.push({ type: "divider" } as MenuItem);
      return acc.concat(section);
   }, []);
};
