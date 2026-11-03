import { usePermissionContext } from "@/context/AppPermissionContext";
import { useProject } from "@kontext-tech/project";
import {
   PROJECT_ROUTE_ERRORS,
   useProjectRouteGuard
} from "@/hooks/useProjectRouteGuard";
import type { RouteConfig } from "@/types";
import { AccessDeniedAlert, AuthenticatedRoute } from "@kontext-tech/auth";
import { shouldRequireAuthentication } from "@kontext-tech/auth";
import { LoadingSpinner, PageErrorBoundary } from "@kontext-tech/ui";
import React, { useMemo } from "react";

/**
 * A wrapper component that handles project-dependent route evaluation
 * Defers authentication checks until project context is available
 */
const ProjectRouteWrapper = ({
   route,
   Element
}: {
   route: RouteConfig;
   Element: React.ComponentType;
}) => {
   const { currentProject, projectNotFound } = useProject();

   const {
      hasRoutePermission,
      resolveRoutePermission,
      isAuthenticated,
      isLoading: permissionLoading
   } = usePermissionContext();

   // Use the centralized guard hook (checks project exists, features)
   const {
      isLoading: guardLoading,
      isReady,
      errorType,
      missingFeatures
   } = useProjectRouteGuard(route);

   // Single source of truth for route policy + evaluation: the registry-derived
   // resolved policy (via the shared permission context), not a local rebuild.
   const routePolicy = useMemo(
      () => resolveRoutePermission(route.name, { project: currentProject }),
      [resolveRoutePermission, route, currentProject]
   );
   const isPublic = routePolicy.isPublic;

   const requiresAuthentication = useMemo(
      () =>
         !isPublic &&
         shouldRequireAuthentication(
            {
               allowedProjectRoles: routePolicy.allowedProjectRoles,
               allowedSystemRoles: routePolicy.allowedSystemRoles,
               allowedPermissionClaims: routePolicy.allowedPermissionClaims
            },
            currentProject
         ),
      [isPublic, routePolicy, currentProject]
   );
   const shouldRedirectToLogin = requiresAuthentication && !isAuthenticated;

   const hasAccess = useMemo(
      () =>
         Boolean(hasRoutePermission(route.name, { project: currentProject })),
      [hasRoutePermission, route, currentProject]
   );

   // Determine overall loading and render state
   const isLoading =
      guardLoading ||
      (!isReady && !errorType) ||
      (!isPublic && permissionLoading);

   if (isLoading) {
      return <LoadingSpinner />;
   }

   if (
      errorType === PROJECT_ROUTE_ERRORS.PROJECT_NOT_FOUND ||
      projectNotFound
   ) {
      return (
         <AccessDeniedAlert
            title="Project Not Found"
            description="The requested project could not be found."
            status="404"
         />
      );
   }

   if (errorType === PROJECT_ROUTE_ERRORS.FEATURE_DISABLED && missingFeatures) {
      return (
         <AccessDeniedAlert
            title="Feature Not Enabled"
            description={`This page requires the following features to be enabled for this project: ${missingFeatures.join(", ")}.`}
         />
      );
   }

   if (shouldRedirectToLogin) {
      return (
         <AuthenticatedRoute loginPath="/login">
            <PageErrorBoundary>
               <Element />
            </PageErrorBoundary>
         </AuthenticatedRoute>
      );
   }

   // If not public and no access granted, deny
   if (!hasAccess) {
      return (
         <AccessDeniedAlert
            title="Access Denied"
            description="You don't have permission to access this page or the feature is not available."
            status="403"
         />
      );
   }

   // Otherwise render the route directly
   return (
      <PageErrorBoundary>
         <Element />
      </PageErrorBoundary>
   );
};

export default ProjectRouteWrapper;
