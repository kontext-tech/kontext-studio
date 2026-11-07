import type {
   PermissionClaim,
   ProjectRole,
   SystemRole
} from "@kontext-tech/auth";
import type {
   ProjectFeature,
   ProjectModel,
   ProjectNavModel
} from "@kontext-tech/schema";
import type {
   SharedLayoutRouteConfig,
   SharedRouteConfig
} from "@kontext-tech/app-runtime/router";
import React from "react";

type StringContextFn = (context: RoutingContextInfo) => string;

export interface RouteDefinition extends SharedRouteConfig<
   RouteNames,
   RoutingContextInfo
> {
   requiresProject?: boolean;
}

export interface RouteNavigationMetadata {
   key?: string | StringContextFn;
   parentKey?: string | StringContextFn;
   label?: string | StringContextFn;
   icon?: string | React.ReactNode;
   /**
    * Optional visibility predicate. When provided, the route is hidden from
    * navigation menus if it returns false. Use server-advertised `features`
    * so visibility is controlled server-side without a frontend redeploy.
    *
    * @example
    * // Show only when the server advertises the feature:
    * visible: ({ features }) => features.includes(SiteFeature.NOTIFICATIONS)
    */
   visible?: (ctx: RouteVisibilityContext) => boolean;
}

export interface RouteAccessPolicy {
   isPublic: boolean | ((context: RoutingContextInfo) => boolean);
   allowedProjectRoles?: ProjectRole[];
   allowedSystemRoles?: SystemRole[];
   allowedPermissionClaims?: PermissionClaim[];
   requiredFeatures?: ProjectFeature[];
}

export interface RouteLayoutMetadata {
   fullWidth?: boolean; // Flag to indicate if route should render as a fluid page
   fullHeight?: boolean; // Flag to indicate if route should use full height with internal scroll
   hideBreadcrumb?: boolean; // Flag to hide breadcrumbs for this route
}

export interface RouteConfig
   extends
      RouteDefinition,
      RouteNavigationMetadata,
      RouteAccessPolicy,
      RouteLayoutMetadata {}

export interface ResolvedRouteAccessPolicy extends Omit<
   RouteAccessPolicy,
   "isPublic"
> {
   isPublic: boolean;
}

/**
 * Context passed to RouteConfig.visible() to determine navigation visibility.
 * Extend this as new feature-flag or role-based conditions are added.
 */
export interface RouteVisibilityContext {
   /**
    * Server-advertised feature flags from SiteConfigResponse.features.
    * Check membership for all UI visibility decisions.
    * @example features.includes(SiteFeature.NOTIFICATIONS)
    */
   features: string[];
}

export type LayoutRouteConfig = SharedLayoutRouteConfig<RouteConfig>;

/**
 * Enum of all route keys used in the application
 * This provides type safety when referencing routes
 */
export enum RouteNames {
   LOGIN = "LOGIN",
   LOCAL_SETUP = "LOCAL_SETUP",
   CLIENT_LOGIN = "CLIENT_LOGIN",
   HOME = "HOME",
   PROJECTS = "PROJECTS",
   ACCOUNT_SETTINGS = "ACCOUNT_SETTINGS",
   USER_MODEL_CONNECTIONS = "USER_MODEL_CONNECTIONS",
   USER_PYTHON_ENVIRONMENT = "USER_PYTHON_ENVIRONMENT",
   PROJECT = "PROJECT",
   PROJECT_CONSOLE = "PROJECT_CONSOLE",
   PROJECT_CATALOGS = "PROJECT_CATALOGS",
   PROJECT_FILES = "PROJECT_FILES",
   PROJECT_KNOWLEDGE = "PROJECT_KNOWLEDGE",
   PROJECT_KNOWLEDGE_DETAIL = "PROJECT_KNOWLEDGE_DETAIL",
   PROJECT_JOBS = "PROJECT_JOBS",
   PROJECT_QUERY_SESSIONS = "PROJECT_QUERY_SESSIONS",
   PROJECT_EVENTS = "PROJECT_EVENTS",
   PROJECT_FILE_DETAIL = "PROJECT_FILE_DETAIL",
   PROJECT_NOTEBOOK_DETAIL = "PROJECT_NOTEBOOK_DETAIL",
   PROJECT_CHAT_SESSIONS = "PROJECT_CHAT_SESSIONS",
   PROJECT_CHAT_SESSION_DETAIL = "PROJECT_CHAT_SESSION_DETAIL",
   PROJECT_SETTINGS = "PROJECT_SETTINGS",
   PROJECT_CHART_DETAIL = "PROJECT_CHART_DETAIL",
   PROJECT_DATA_TABLE_DETAIL = "PROJECT_DATA_TABLE_DETAIL",
   NOT_FOUND = "NOT_FOUND"
}

export interface RoutingContextInfo {
   project?: ProjectNavModel | ProjectModel | null;
   additionalInfo?: Record<string, string>;
}
