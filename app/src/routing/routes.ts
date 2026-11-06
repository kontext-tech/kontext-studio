// Define both route paths and menu structure in one place.
import {
   RouteNames,
   type LayoutRouteConfig,
   type RouteConfig,
   type RoutingContextInfo
} from "@/types";
import { PERMISSION_CLAIMS, SYSTEM_ROLES } from "@kontext-labs/auth";
import { getSafeIconByName } from "@kontext-labs/icons";
import { AccessLevel, ProjectFeature, SiteFeature } from "@kontext-labs/schema";
import { withSuspense } from "@kontext-labs/ui";
import { lazy } from "react";
import { RouteRegistry } from "./RouteRegistry";

// Lazy load components using direct imports
const LoginPage = lazy(() => import("../features/auth/screens/LoginPage"));
const ClientAuthenticationPage = lazy(
   () => import("../features/auth/screens/ClientAuthenticationPage")
);
const LocalSetupPage = lazy(
   () => import("../features/auth/screens/LocalSetupPage")
);
const ProjectsRedirectPage = lazy(
   () => import("../features/projects/screens/ProjectsRedirectPage")
);
const FileListPage = lazy(
   () => import("../features/files/screens/FileListPage")
);
const FileDetailPage = lazy(
   () => import("../features/files/screens/FileDetailPage")
);
const NotebookDetailPage = lazy(
   () => import("../features/files/screens/NotebookDetailPage")
);
const ChartDetailPage = lazy(
   () => import("../features/files/screens/ChartDetailPage")
);
const DataTableDetailPage = lazy(
   () => import("../features/files/screens/DataTableDetailPage")
);
const ProjectHomePage = lazy(
   () => import("../features/projects/screens/ProjectHomePage")
);
const ProjectCatalogsPage = lazy(
   () => import("../features/projects/screens/ProjectCatalogsPage")
);
const KnowledgeListPage = lazy(
   () => import("../features/knowledge/screens/KnowledgeListPage")
);
const KnowledgeDetailPage = lazy(
   () => import("../features/knowledge/screens/KnowledgeDetailPage")
);
const ProjectNewChatPage = lazy(
   () => import("../features/chat/screens/ProjectNewChatPage")
);
const ProjectSettingsPage = lazy(
   () => import("../features/projects/screens/ProjectSettingsPage")
);
const ProjectJobsPage = lazy(
   () => import("../features/projects/screens/ProjectJobsPage")
);
const ProjectQuerySessionsPage = lazy(
   () => import("../features/projects/screens/ProjectQuerySessionsPage")
);
const ProjectEventsPage = lazy(
   () => import("../features/projects/screens/ProjectEventsPage")
);
const ChatSessionListPage = lazy(
   () => import("../features/chat/screens/ChatSessionListPage")
);
const ChatSessionDetailPage = lazy(
   () => import("../features/chat/screens/ChatSessionDetailPage")
);
const NotFoundPage = lazy(() => import("../app/screens/NotFoundPage"));
const HomePage = lazy(() => import("../features/account/screens/HomePage"));
const AccountPage = lazy(
   () => import("../features/account/screens/AccountPage")
);
const ModelProvidersPage = lazy(
   () => import("../features/account/screens/ModelProvidersPage")
);
const PythonEnvironmentPage = lazy(
   () => import("../features/account/screens/PythonEnvironmentPage")
);

const AuthLayout = lazy(() => import("../layouts/AuthLayout"));
const ProjectLayout = lazy(() => import("../layouts/ProjectLayout"));
const UserLayout = lazy(() => import("../layouts/UserLayout"));

// Define the route configuration with metadata for menus, breadcrumbs and routes
export const ROUTE_CONFIG: {
   [key in RouteNames]: RouteConfig;
} = {
   [RouteNames.LOGIN]: {
      path: "/login",
      pathPattern: "/login",
      name: RouteNames.LOGIN,
      label: "Sign In",
      layout: AuthLayout,
      element: () => withSuspense(LoginPage),
      isPublic: true
   },
   [RouteNames.LOCAL_SETUP]: {
      path: "/setup",
      pathPattern: "/setup",
      name: RouteNames.LOCAL_SETUP,
      label: "Local Setup",
      layout: AuthLayout,
      element: () => withSuspense(LocalSetupPage),
      isPublic: true,
      visible: ({ features }) => features.includes(SiteFeature.LOCAL_MODE)
   },
   [RouteNames.CLIENT_LOGIN]: {
      path: "/client-login",
      pathPattern: "/client-login",
      name: RouteNames.CLIENT_LOGIN,
      label: "Client Authentication",
      layout: AuthLayout,
      element: () => withSuspense(ClientAuthenticationPage),
      isPublic: true
   },
   [RouteNames.HOME]: {
      path: "/",
      pathPattern: "/",
      name: RouteNames.HOME,
      key: "home",
      label: "Home",
      icon: "HomeOutlined",
      layout: UserLayout,
      element: () => withSuspense(HomePage),
      isPublic: false,
      fullWidth: false
   },
   [RouteNames.PROJECTS]: {
      path: "/projects",
      pathPattern: "/projects",
      name: RouteNames.PROJECTS,
      key: "projects",
      label: "Projects",
      icon: "ProjectsOutlined",
      parentKey: "home",
      layout: UserLayout,
      element: () => withSuspense(ProjectsRedirectPage),
      isPublic: false,
      visible: () => false
   },
   [RouteNames.ACCOUNT_SETTINGS]: {
      path: "/account",
      pathPattern: "/account",
      name: RouteNames.ACCOUNT_SETTINGS,
      key: "account",
      label: "Account Settings",
      icon: "UserOutlined",
      parentKey: "home",
      layout: UserLayout,
      element: () => withSuspense(AccountPage),
      isPublic: false,
      visible: ({ features }) => features.includes(SiteFeature.LOCAL_MODE)
   },
   [RouteNames.USER_MODEL_CONNECTIONS]: {
      path: "/llm-providers",
      pathPattern: "/llm-providers",
      name: RouteNames.USER_MODEL_CONNECTIONS,
      key: "llm-providers",
      label: "LLM Providers",
      icon: "SettingOutlined",
      parentKey: "home",
      layout: UserLayout,
      element: () => withSuspense(ModelProvidersPage),
      isPublic: false,
      visible: ({ features }) =>
         features.includes(SiteFeature.MODEL_CONNECTIONS)
   },
   [RouteNames.USER_PYTHON_ENVIRONMENT]: {
      path: "/python-environment",
      pathPattern: "/python-environment",
      name: RouteNames.USER_PYTHON_ENVIRONMENT,
      key: "python-environment",
      label: "Python Environment",
      icon: "CodeOutlined",
      parentKey: "home",
      layout: UserLayout,
      element: () => withSuspense(PythonEnvironmentPage),
      isPublic: false,
      visible: ({ features }) =>
         features.includes(SiteFeature.PYTHON_ENVIRONMENT)
   },
   [RouteNames.PROJECT]: {
      path: (context: RoutingContextInfo) =>
         `/project/${context.project?.projectCode}`,
      pathPattern: "/project/:projectCode",
      name: RouteNames.PROJECT,
      key: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-new-chat`,
      label: "New Chat",
      icon: "PlusOutlined",
      layout: ProjectLayout,
      element: () => withSuspense(ProjectNewChatPage),
      isPublic: (context: RoutingContextInfo) =>
         context.project?.accessLevel === AccessLevel.Public,
      allowedPermissionClaims: [PERMISSION_CLAIMS.PROJECTS_READ],
      fullWidth: true,
      fullHeight: true
   },
   [RouteNames.PROJECT_CONSOLE]: {
      path: (context: RoutingContextInfo) =>
         `/project/${context.project?.projectCode}/console`,
      pathPattern: "/project/:projectCode/console",
      name: RouteNames.PROJECT_CONSOLE,
      key: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-console`,
      label: "Overview",
      icon: "DashboardOutlined",
      layout: ProjectLayout,
      element: () => withSuspense(ProjectHomePage),
      isPublic: (context: RoutingContextInfo) =>
         context.project?.accessLevel === AccessLevel.Public,
      allowedPermissionClaims: [PERMISSION_CLAIMS.PROJECTS_READ]
   },
   [RouteNames.PROJECT_CATALOGS]: {
      path: (context: RoutingContextInfo) =>
         `/project/${context.project?.projectCode}/catalogs`,
      pathPattern: "/project/:projectCode/catalogs",
      name: RouteNames.PROJECT_CATALOGS,
      key: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-catalogs`,
      parentKey: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-console`,
      label: "Data Sources",
      icon: "DatabaseOutlined",
      layout: ProjectLayout,
      element: () => withSuspense(ProjectCatalogsPage),
      isPublic: false,
      allowedPermissionClaims: [PERMISSION_CLAIMS.PROJECTS_READ]
   },
   [RouteNames.PROJECT_SETTINGS]: {
      path: (context: RoutingContextInfo) =>
         `/project/${context.project?.projectCode}/settings`,
      pathPattern: "/project/:projectCode/settings",
      name: RouteNames.PROJECT_SETTINGS,
      key: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-settings`,
      parentKey: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-console`,
      label: "Settings",
      icon: "SettingOutlined",
      layout: ProjectLayout,
      element: () => withSuspense(ProjectSettingsPage),
      isPublic: false,
      allowedPermissionClaims: [PERMISSION_CLAIMS.PROJECTS_UPDATE]
   },
   [RouteNames.PROJECT_CHAT_SESSIONS]: {
      path: (context: RoutingContextInfo) =>
         `/project/${context.project?.projectCode}/chats`,
      pathPattern: "/project/:projectCode/chats",
      name: RouteNames.PROJECT_CHAT_SESSIONS,
      key: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-chats`,
      parentKey: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-console`,
      label: "Chats",
      icon: "MessageOutlined",
      layout: ProjectLayout,
      element: () => withSuspense(ChatSessionListPage),
      isPublic: false,
      allowedPermissionClaims: [PERMISSION_CLAIMS.CHATSESSIONS_READ],
      requiredFeatures: [ProjectFeature.Chat]
   },
   [RouteNames.PROJECT_CHAT_SESSION_DETAIL]: {
      path: (context: RoutingContextInfo) =>
         `/project/${context.project?.projectCode}/chat/${context.additionalInfo?.sessionId}`,
      pathPattern: "/project/:projectCode/chat/:chatSessionId",
      name: RouteNames.PROJECT_CHAT_SESSION_DETAIL,
      key: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-chat-${context.additionalInfo?.sessionId}`,
      parentKey: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-chats`,
      label: (context: RoutingContextInfo) =>
         context.additionalInfo?.sessionName || "Chat Session",
      icon: "MessageOutlined",
      layout: ProjectLayout,
      element: () => withSuspense(ChatSessionDetailPage),
      isPublic: false,
      allowedPermissionClaims: [PERMISSION_CLAIMS.CHATSESSIONS_READ],
      requiredFeatures: [ProjectFeature.Chat],
      fullWidth: true,
      fullHeight: true
   },
   [RouteNames.PROJECT_FILES]: {
      path: (context: RoutingContextInfo) =>
         `/project/${context.project?.projectCode}/files`,
      pathPattern: "/project/:projectCode/files",
      name: RouteNames.PROJECT_FILES,
      key: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-files`,
      parentKey: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-console`,
      label: "Files",
      icon: "FileOutlined",
      layout: ProjectLayout,
      element: () => withSuspense(FileListPage),
      isPublic: (context: RoutingContextInfo) =>
         context.project?.accessLevel === AccessLevel.Public,
      allowedPermissionClaims: [PERMISSION_CLAIMS.RESOURCES_READ]
   },
   [RouteNames.PROJECT_KNOWLEDGE]: {
      path: (context: RoutingContextInfo) =>
         `/project/${context.project?.projectCode}/knowledge`,
      pathPattern: "/project/:projectCode/knowledge",
      name: RouteNames.PROJECT_KNOWLEDGE,
      key: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-knowledge`,
      parentKey: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-console`,
      label: "Knowledge",
      icon: "BookOutlined",
      layout: ProjectLayout,
      element: () => withSuspense(KnowledgeListPage),
      isPublic: false,
      allowedPermissionClaims: [PERMISSION_CLAIMS.PROJECTS_READ]
   },
   [RouteNames.PROJECT_KNOWLEDGE_DETAIL]: {
      path: (context: RoutingContextInfo) =>
         `/project/${context.project?.projectCode}/knowledge/${context.additionalInfo?.conceptId}`,
      pathPattern: "/project/:projectCode/knowledge/*",
      name: RouteNames.PROJECT_KNOWLEDGE_DETAIL,
      key: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-knowledge-${context.additionalInfo?.conceptId}`,
      parentKey: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-knowledge`,
      label: "Concept",
      icon: "BookOutlined",
      layout: ProjectLayout,
      element: () => withSuspense(KnowledgeDetailPage),
      isPublic: false,
      allowedPermissionClaims: [PERMISSION_CLAIMS.PROJECTS_READ]
   },
   [RouteNames.PROJECT_JOBS]: {
      path: (context: RoutingContextInfo) =>
         `/project/${context.project?.projectCode}/jobs`,
      pathPattern: "/project/:projectCode/jobs",
      name: RouteNames.PROJECT_JOBS,
      key: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-jobs`,
      parentKey: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-console`,
      label: "Jobs",
      icon: "PlayCircleOutlined",
      layout: ProjectLayout,
      element: () => withSuspense(ProjectJobsPage),
      isPublic: false,
      allowedPermissionClaims: [PERMISSION_CLAIMS.JOBS_READ]
   },
   [RouteNames.PROJECT_QUERY_SESSIONS]: {
      path: (context: RoutingContextInfo) =>
         `/project/${context.project?.projectCode}/queries`,
      pathPattern: "/project/:projectCode/queries",
      name: RouteNames.PROJECT_QUERY_SESSIONS,
      key: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-queries`,
      parentKey: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-console`,
      label: "Query Session History",
      icon: "HistoryOutlined",
      layout: ProjectLayout,
      element: () => withSuspense(ProjectQuerySessionsPage),
      isPublic: false,
      allowedSystemRoles: [SYSTEM_ROLES.ADMINISTRATOR],
      allowedPermissionClaims: [PERMISSION_CLAIMS.QUERYSESSIONS_READ]
   },
   [RouteNames.PROJECT_EVENTS]: {
      path: (context: RoutingContextInfo) =>
         `/project/${context.project?.projectCode}/activity`,
      pathPattern: "/project/:projectCode/activity",
      name: RouteNames.PROJECT_EVENTS,
      key: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-activity`,
      parentKey: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-console`,
      label: "Activity Log",
      icon: "BellOutlined",
      layout: ProjectLayout,
      element: () => withSuspense(ProjectEventsPage),
      isPublic: false,
      allowedSystemRoles: [SYSTEM_ROLES.ADMINISTRATOR],
      allowedPermissionClaims: [PERMISSION_CLAIMS.EVENTS_READ]
   },
   [RouteNames.PROJECT_FILE_DETAIL]: {
      path: (context: RoutingContextInfo) =>
         `/project/${context.project?.projectCode}/file/${context.additionalInfo?.fileId}`,
      pathPattern: "/project/:projectCode/file/:fileId",
      name: RouteNames.PROJECT_FILE_DETAIL,
      key: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-file-${context.additionalInfo?.fileId}`,
      parentKey: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-files`,
      label: (context: RoutingContextInfo) =>
         context.additionalInfo?.fileName || "File Details",
      layout: ProjectLayout,
      element: () => withSuspense(FileDetailPage),
      isPublic: (context: RoutingContextInfo) =>
         context.project?.accessLevel === AccessLevel.Public,
      allowedPermissionClaims: [PERMISSION_CLAIMS.RESOURCES_READ],
      fullWidth: true,
      fullHeight: true
   },
   [RouteNames.PROJECT_NOTEBOOK_DETAIL]: {
      path: (context: RoutingContextInfo) =>
         `/project/${context.project?.projectCode}/notebook/${context.additionalInfo?.fileId}`,
      pathPattern: "/project/:projectCode/notebook/:fileId",
      name: RouteNames.PROJECT_NOTEBOOK_DETAIL,
      key: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-notebook-${context.additionalInfo?.fileId}`,
      parentKey: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-files`,
      label: (context: RoutingContextInfo) =>
         context.additionalInfo?.fileName || "Notebook Details",
      layout: ProjectLayout,
      element: () => withSuspense(NotebookDetailPage),
      isPublic: false,
      allowedPermissionClaims: [PERMISSION_CLAIMS.RESOURCES_READ],
      fullWidth: true,
      fullHeight: true
   },
   [RouteNames.PROJECT_CHART_DETAIL]: {
      path: (context: RoutingContextInfo) =>
         `/project/${context.project?.projectCode}/chart/${context.additionalInfo?.fileId}`,
      pathPattern: "/project/:projectCode/chart/:fileId",
      name: RouteNames.PROJECT_CHART_DETAIL,
      key: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-chart-${context.additionalInfo?.fileId}`,
      parentKey: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-files`,
      label: (context: RoutingContextInfo) =>
         context.additionalInfo?.fileName || "Chart Details",
      layout: ProjectLayout,
      element: () => withSuspense(ChartDetailPage),
      isPublic: false,
      allowedPermissionClaims: [PERMISSION_CLAIMS.RESOURCES_READ],
      fullWidth: true,
      fullHeight: true
   },
   [RouteNames.PROJECT_DATA_TABLE_DETAIL]: {
      path: (context: RoutingContextInfo) =>
         `/project/${context.project?.projectCode}/data-table/${context.additionalInfo?.fileId}`,
      pathPattern: "/project/:projectCode/data-table/:fileId",
      name: RouteNames.PROJECT_DATA_TABLE_DETAIL,
      key: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-data-table-${context.additionalInfo?.fileId}`,
      parentKey: (context: RoutingContextInfo) =>
         `project-${context.project?.projectCode}-files`,
      label: (context: RoutingContextInfo) =>
         context.additionalInfo?.fileName || "Data Table Details",
      layout: ProjectLayout,
      element: () => withSuspense(DataTableDetailPage),
      isPublic: false,
      allowedPermissionClaims: [PERMISSION_CLAIMS.RESOURCES_READ],
      fullWidth: true,
      fullHeight: true
   },
   [RouteNames.NOT_FOUND]: {
      path: "*",
      pathPattern: "*",
      name: RouteNames.NOT_FOUND,
      label: "Page Not Found",
      layout: AuthLayout,
      element: () => withSuspense(NotFoundPage),
      isPublic: true
   }
};

/**
 * Generates a LayoutRouteConfig array from the ROUTE_CONFIG
 * This allows for dynamic routing configuration based on the current project context
 *
 * @param contextInfo Optional routing context info for dynamic routes
 * @returns LayoutRouteConfig[] ready to be used with renderRoutes
 */
export const routeRegistry = new RouteRegistry(ROUTE_CONFIG);

export const getLayoutRouteConfig = (
   contextInfo?: RoutingContextInfo
): LayoutRouteConfig[] =>
   routeRegistry.getLayoutRouteConfig(
      contextInfo,
      (routeName) =>
         !(routeName === RouteNames.CLIENT_LOGIN && import.meta.env.PROD)
   );

export const getRouteKey = (
   routeConfig: RouteConfig,
   context?: RoutingContextInfo
): string | undefined => routeRegistry.getRouteKey(routeConfig, context);

/**
 * Gets the parent key for a given route name with optional context information
 *
 * @param routeName The route name to get the parent key for
 * @param context Optional context information for dynamic parent keys
 * @returns The parent key for the given route or undefined if not specified
 */
export const getRouteHierarchy = (
   routeName: RouteNames,
   context?: RoutingContextInfo
): RouteConfig[] => routeRegistry.getRouteHierarchy(routeName, context);

/**
 * Gets the route configuration for a given route name with optional context information
 *
 * @param routeName The route name to get the configuration for
 * @param context Optional context information for dynamic routes
 * @returns The RouteConfig object for the given route
 */
export const getRouteConfig = (
   routeName: RouteNames,
   context?: RoutingContextInfo
): RouteConfig => {
   const routeConfig = routeRegistry.getRouteConfig(routeName, context);

   return {
      ...routeConfig,
      icon:
         typeof routeConfig.icon === "string"
            ? getSafeIconByName(routeConfig.icon)
            : routeConfig.icon
   };
};
