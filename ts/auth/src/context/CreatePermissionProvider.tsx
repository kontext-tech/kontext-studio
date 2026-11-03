import type { PermissionClaim } from "../constants/permissionClaims";
import type { ProjectRole } from "../constants/ProjectRole";
import type { SystemRole } from "../constants/systemRoles";
import type { PermissionProps } from "../permissionTypes";
import {
   evaluatePermission,
   evaluatePermissionClaims,
   evaluateSystemRoles,
   type PermissionCheckOptions
} from "../utils/permissionEvaluator";
import { SystemRoleUtils } from "../utils/systemRoleUtils";
import {
   PermissionContext,
   type PermissionContextValue
} from "./PermissionContext";
import type {
   ProjectFeature,
   ProjectModel,
   ProjectNavModel
} from "@kontext-tech/schema";
import React, { useMemo } from "react";

type ProjectLike = ProjectModel | ProjectNavModel | null | undefined;

export interface ResolvedRoutePermission {
   isPublic: boolean;
   project?: ProjectModel | null;
   allowedProjectRoles?: ProjectRole[];
   allowedSystemRoles?: SystemRole[];
   allowedPermissionClaims?: PermissionClaim[];
   requiredFeatures?: ProjectFeature[];
}

export interface ResolvedPermissionProviderState<
   TRouteName extends string = string,
   TRouteContext = unknown
> {
   isLoading: boolean;
   isAuthenticated: boolean;
   userId?: string;
   userSystemRoles?: SystemRole[];
   userPermissionClaims?: PermissionClaim[];
   currentProject?: ProjectModel | null;
   getProjectRoles?: (project?: ProjectLike) => ProjectRole[];
   resolveRoutePermission?: (
      routeName: TRouteName,
      context?: TRouteContext
   ) => ResolvedRoutePermission | null;
}

const normalizeProject = (project?: ProjectLike): ProjectModel | null => {
   if (!project) {
      return null;
   }

   if ("configuration" in project || "_configuration" in project) {
      return project as ProjectModel;
   }

   return null;
};

export const createPermissionContextValue = <
   TRouteName extends string = string,
   TRouteContext = unknown
>(
   state: ResolvedPermissionProviderState<TRouteName, TRouteContext>
): PermissionContextValue => {
   const {
      isLoading,
      isAuthenticated,
      userId,
      userSystemRoles = [],
      userPermissionClaims = [],
      currentProject,
      getProjectRoles,
      resolveRoutePermission
   } = state;

   return {
      hasPermission: (
         checkOptions: PermissionProps,
         project?: ProjectModel | null
      ) => {
         const targetProject = project ?? currentProject;
         return evaluatePermission(checkOptions as PermissionCheckOptions, {
            isAuthenticated,
            project: targetProject,
            userId,
            userSystemRoles,
            userPermissionClaims,
            userProjectRoles: getProjectRoles?.(targetProject) ?? []
         });
      },
      isAdministrator: () =>
         isAuthenticated && SystemRoleUtils.isAdministrator(userSystemRoles),
      hasSystemRole: (roles: SystemRole[]) =>
         isAuthenticated && evaluateSystemRoles(roles, userSystemRoles),
      hasPermissionClaim: (claims: PermissionClaim[], resource?: unknown) =>
         isAuthenticated &&
         evaluatePermissionClaims(
            claims,
            userPermissionClaims,
            getProjectRoles?.(normalizeProject(resource as ProjectLike)) ?? []
         ),
      hasRoutePermission: resolveRoutePermission
         ? (routeName: string, context?: unknown) => {
              const routePermission = resolveRoutePermission(
                 routeName as TRouteName,
                 context as TRouteContext
              );

              if (!routePermission) {
                 return false;
              }

              if (routePermission.isPublic) {
                 return true;
              }

              return evaluatePermission(
                 {
                    allowedProjectRoles: routePermission.allowedProjectRoles,
                    allowedSystemRoles: routePermission.allowedSystemRoles,
                    allowedPermissionClaims:
                       routePermission.allowedPermissionClaims,
                    requiredFeatures: routePermission.requiredFeatures,
                    requireAuthenticated: !routePermission.isPublic
                 },
                 {
                    isAuthenticated,
                    project: routePermission.project ?? currentProject,
                    userId,
                    userSystemRoles,
                    userPermissionClaims,
                    userProjectRoles:
                       getProjectRoles?.(
                          routePermission.project ?? currentProject
                       ) ?? []
                 }
              );
           }
         : undefined,
      isLoading,
      isAuthenticated
   };
};

export const createPermissionProvider = <
   TRouteName extends string = string,
   TRouteContext = unknown
>(
   useResolvedState: () => ResolvedPermissionProviderState<
      TRouteName,
      TRouteContext
   >
) => {
   const PermissionProvider: React.FC<{ children: React.ReactNode }> = ({
      children
   }) => {
      const state = useResolvedState();
      const value = useMemo(() => createPermissionContextValue(state), [state]);

      return (
         <PermissionContext.Provider value={value}>
            {children}
         </PermissionContext.Provider>
      );
   };

   return PermissionProvider;
};
