import { useProject } from "@kontext-labs/project";
import { useUser } from "@kontext-labs/identity";
import { routeRegistry } from "@/routing";
import type { RoutingContextInfo } from "@/types";
import { RouteNames } from "@/types";
import {
   PermissionContext as SharedPermissionContext,
   createPermissionContextValue,
   type PermissionContextValue as SharedPermissionContextValue
} from "@kontext-labs/auth";
import type { PermissionClaim, SystemRole } from "@kontext-labs/auth";
import { CommonRoleGroups, ProjectRole } from "@kontext-labs/auth";
import {
   evaluateExplicitUserAccess,
   evaluateProjectRoles,
   evaluateRequiredFeatures,
   type PermissionCheckOptions
} from "@kontext-labs/auth";
import { type ProjectFeature, type ProjectModel } from "@kontext-labs/schema";
import type { ProjectNavModel } from "@kontext-labs/schema";
import React, { createContext, useCallback, useContext, useMemo } from "react";

type PermissionContextValue = Omit<
   SharedPermissionContextValue,
   "hasPermission" | "hasPermissionClaim" | "hasRoutePermission"
> & {
   hasAtLeastOneRole: (
      allowedRoles?: ProjectRole[],
      project?: ProjectModel | null
   ) => boolean;
   hasRequiredFeatures: (
      requiredFeatures: ProjectFeature[],
      project?: ProjectModel | null
   ) => boolean;
   hasPermission: (
      checkOptions: PermissionCheckOptions,
      project?: ProjectModel | null,
      context?: { ownerId?: string }
   ) => boolean;

   canContributeToProject: (project?: ProjectModel | null) => boolean;
   isProjectAdmin: (project?: ProjectModel | null) => boolean;
   isProjectOwner: (project?: ProjectModel | null) => boolean;
   canEditProject: (project?: ProjectModel | null) => boolean;
   hasPermissionClaim: (
      claims: PermissionClaim[],
      resource?: unknown
   ) => boolean;
   isUserExplicitlyAllowed: (
      allowedUserIds?: string[],
      ownerId?: string
   ) => boolean;
   hasRoutePermission: (
      routeName: RouteNames,
      context?: RoutingContextInfo
   ) => boolean;
   resolveRoutePermission: (
      routeName: RouteNames,
      context?: RoutingContextInfo
   ) => {
      isPublic: boolean;
      allowedProjectRoles?: ProjectRole[];
      allowedSystemRoles?: SystemRole[];
      allowedPermissionClaims?: PermissionClaim[];
      requiredFeatures?: ProjectFeature[];
   };

   currentProject: ProjectModel | null;
   projectNotFound: boolean;
};

const AppPermissionContext = createContext<PermissionContextValue | null>(null);

export const PermissionProvider: React.FC<{ children: React.ReactNode }> = ({
   children
}) => {
   const { currentProject, isProjectLoading, projectNotFound } = useProject();
   const {
      isLoading: isUserLoading,
      getUserRolesForProject,
      hasProjectRole,
      user,
      isAuthenticated
   } = useUser();

   const isLoading = isProjectLoading || isUserLoading;
   const userSystemRoles = useMemo(
      () => (user?.roles as SystemRole[] | undefined) ?? [],
      [user?.roles]
   );
   const userPermissionClaims = useMemo(
      () => (user?.permissionClaims as PermissionClaim[] | undefined) ?? [],
      [user?.permissionClaims]
   );

   const getProjectRolesForPermissionCheck = useCallback(
      (project?: ProjectModel | ProjectNavModel | null): ProjectRole[] => {
         const targetProject = project || currentProject;

         if (isLoading || !targetProject?.id) {
            return [];
         }

         return getUserRolesForProject(targetProject.id) as ProjectRole[];
      },
      [currentProject, getUserRolesForProject, isLoading]
   );

   /**
    * Checks if the user is explicitly allowed by user ID or ownership
    */
   const isUserExplicitlyAllowed = useCallback(
      (allowedUserIds?: string[], ownerId?: string): boolean => {
         return evaluateExplicitUserAccess(user?.id, allowedUserIds, ownerId);
      },
      [user]
   );

   /**
    * Checks if the project has all the required features enabled
    */
   const hasRequiredFeatures = useCallback(
      (
         requiredFeatures: ProjectFeature[],
         project?: ProjectModel | null
      ): boolean => {
         const targetProject = project || currentProject;

         if (isLoading || !targetProject) {
            return false;
         }

         return evaluateRequiredFeatures(requiredFeatures, targetProject);
      },
      [currentProject, isLoading]
   );

   /**
    * Checks if the user has at least one of the specified roles in the project
    */
   const hasAtLeastOneRole = useCallback(
      (
         allowedRoles?: ProjectRole[],
         project?: ProjectModel | null
      ): boolean => {
         const targetProject = project || currentProject;

         if (isLoading || !targetProject?.id) {
            return false;
         }

         return evaluateProjectRoles(
            allowedRoles,
            targetProject,
            getProjectRolesForPermissionCheck(targetProject)
         );
      },
      [currentProject, getProjectRolesForPermissionCheck, isLoading]
   );

   /**
    * Checks if the user has CONTRIBUTOR permissions
    */
   const canContributeToProject = useCallback(
      (project?: ProjectModel | null): boolean =>
         hasAtLeastOneRole(CommonRoleGroups.CONTENT_EDITORS, project),
      [hasAtLeastOneRole]
   );

   /**
    * Checks if the user has ADMIN permissions
    */
   const isProjectAdmin = useCallback(
      (project?: ProjectModel | null): boolean =>
         hasAtLeastOneRole(CommonRoleGroups.PROJECT_MANAGERS, project),
      [hasAtLeastOneRole]
   );

   /**
    * Checks if the user is the OWNER of the project
    */
   const isProjectOwner = useCallback(
      (project?: ProjectModel | null): boolean => {
         const targetProject = project || currentProject;
         if (!targetProject?.id) {
            return false;
         }
         return hasProjectRole(targetProject.id, ProjectRole.OWNER);
      },
      [currentProject, hasProjectRole]
   );

   /**
    * Checks if the user can edit project settings (requires ADMIN or OWNER)
    */
   const canEditProject = useCallback(
      (project?: ProjectModel | null): boolean =>
         hasAtLeastOneRole(CommonRoleGroups.PROJECT_MANAGERS, project) ||
         isProjectOwner(project),
      [hasAtLeastOneRole, isProjectOwner]
   );

   const resolveRoutePermission = useCallback(
      (routeName: RouteNames, context?: RoutingContextInfo) => {
         const accessPolicy = routeRegistry.getAccessPolicy(routeName, context);
         const routingContext = context ?? null;
         const projectForPermission =
            routingContext?.project &&
            "_configuration" in routingContext.project
               ? (routingContext.project as ProjectModel)
               : (routingContext?.project as ProjectModel | null);

         return {
            isPublic: accessPolicy.isPublic,
            project: projectForPermission ?? currentProject,
            allowedProjectRoles: accessPolicy.allowedProjectRoles,
            allowedSystemRoles: accessPolicy.allowedSystemRoles,
            allowedPermissionClaims: accessPolicy.allowedPermissionClaims,
            requiredFeatures: accessPolicy.requiredFeatures
         };
      },
      [currentProject]
   );

   // Shared @kontext-labs/auth context consumed by extracted package components.
   const sharedContextValue = useMemo(
      (): SharedPermissionContextValue =>
         createPermissionContextValue({
            isLoading,
            isAuthenticated,
            userId: user?.id,
            currentProject,
            userSystemRoles,
            userPermissionClaims,
            getProjectRoles: (project) =>
               getProjectRolesForPermissionCheck(project ?? currentProject),
            resolveRoutePermission: (routeName, context) =>
               resolveRoutePermission(
                  routeName as RouteNames,
                  context as RoutingContextInfo | undefined
               )
         }),
      [
         currentProject,
         getProjectRolesForPermissionCheck,
         isAuthenticated,
         isLoading,
         resolveRoutePermission,
         user?.id,
         userPermissionClaims,
         userSystemRoles
      ]
   );

   /**
    * Comprehensive permission check. The evaluation itself lives in
    * @kontext-labs/auth (createPermissionContextValue); this context only
    * defaults the project argument to the current project.
    */
   const hasPermission = useCallback(
      (
         checkOptions: PermissionCheckOptions = {},
         project?: ProjectModel | null
      ): boolean =>
         sharedContextValue.hasPermission(
            checkOptions,
            project || currentProject
         ),
      [sharedContextValue, currentProject]
   );

   const contextValue = useMemo(
      (): PermissionContextValue => ({
         ...sharedContextValue,
         hasPermission,
         hasAtLeastOneRole,
         hasRequiredFeatures,
         canContributeToProject,
         isProjectAdmin,
         isProjectOwner,
         canEditProject,
         isUserExplicitlyAllowed,
         hasRoutePermission:
            sharedContextValue.hasRoutePermission as PermissionContextValue["hasRoutePermission"],
         resolveRoutePermission: (
            routeName: RouteNames,
            context?: RoutingContextInfo
         ) =>
            resolveRoutePermission(routeName, context) as ReturnType<
               PermissionContextValue["resolveRoutePermission"]
            >,
         currentProject,
         projectNotFound
      }),
      [
         sharedContextValue,
         hasPermission,
         hasAtLeastOneRole,
         resolveRoutePermission,
         hasRequiredFeatures,
         canContributeToProject,
         isProjectAdmin,
         isProjectOwner,
         canEditProject,
         isUserExplicitlyAllowed,
         currentProject,
         projectNotFound
      ]
   );

   return (
      <SharedPermissionContext.Provider value={sharedContextValue}>
         <AppPermissionContext.Provider value={contextValue}>
            {children}
         </AppPermissionContext.Provider>
      </SharedPermissionContext.Provider>
   );
};

// eslint-disable-next-line react-refresh/only-export-components
export const usePermissionContext = () => {
   const context = useContext(AppPermissionContext);
   if (!context) {
      throw new Error(
         "usePermissionContext must be used within PermissionProvider"
      );
   }
   return context;
};
