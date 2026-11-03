import { logger } from "@kontext-labs/common";
import { useProject } from "@kontext-labs/project";
import type { RouteConfig } from "@/types";
import { useParams } from "react-router-dom";

export const PROJECT_ROUTE_ERRORS = {
   PROJECT_NOT_FOUND: "PROJECT_NOT_FOUND",
   PROJECT_MISMATCH: "PROJECT_MISMATCH",
   FEATURE_DISABLED: "FEATURE_DISABLED"
} as const;

export type ProjectRouteErrorType =
   (typeof PROJECT_ROUTE_ERRORS)[keyof typeof PROJECT_ROUTE_ERRORS];

export interface ProjectRouteGuardResult {
   isLoading: boolean;
   isReady: boolean;
   errorType?: ProjectRouteErrorType;
   missingFeatures?: string[];
}

/**
 * Hook to centralize project-dependent route validation logic.
 * Checks for project existence, consistency with URL, and feature flags.
 */
export const useProjectRouteGuard = (
   route: RouteConfig
): ProjectRouteGuardResult => {
   const { currentProject, isProjectLoading, projectNotFound } = useProject();
   const { projectCode } = useParams<{ projectCode?: string }>();

   // A route is project-dependent if it has the requiresProject flag set or if the path pattern contains :projectCode
   const routeDependsOnProject =
      route.requiresProject ??
      (route.pathPattern && route.pathPattern.includes(":projectCode")) ??
      false;

   // 1. Check if we are waiting for project to load
   if (
      routeDependsOnProject &&
      projectCode &&
      isProjectLoading &&
      !currentProject &&
      !projectNotFound
   ) {
      return { isLoading: true, isReady: false };
   }

   // 2. Check for project mismatch (Race condition protection)
   if (
      routeDependsOnProject &&
      projectCode &&
      currentProject &&
      currentProject.projectCode.toLowerCase() !== projectCode.toLowerCase() &&
      !projectNotFound
   ) {
      logger.debug(
         `[ProjectRouteGuard] Project mismatch: context="${currentProject.projectCode}", URL="${projectCode}". Waiting for sync...`
      );
      return {
         isLoading: true,
         isReady: false,
         errorType: PROJECT_ROUTE_ERRORS.PROJECT_MISMATCH
      };
   }

   // 3. Check for required features
   if (routeDependsOnProject && currentProject && route.requiredFeatures) {
      const enabledFeatures = currentProject.configuration?.features || [];
      const missingFeatures = route.requiredFeatures.filter(
         (f) => !enabledFeatures.includes(f)
      );

      if (missingFeatures.length > 0) {
         return {
            isLoading: false,
            isReady: false,
            errorType: PROJECT_ROUTE_ERRORS.FEATURE_DISABLED,
            missingFeatures
         };
      }
   }

   // 4. Project Not Found is handled by the page itself usually, or we can flag it here
   if (routeDependsOnProject && projectNotFound) {
      return {
         isLoading: false,
         isReady: false,
         errorType: PROJECT_ROUTE_ERRORS.PROJECT_NOT_FOUND
      };
   }

   // 5. Return ready if all checks pass
   return { isLoading: false, isReady: true };
};
