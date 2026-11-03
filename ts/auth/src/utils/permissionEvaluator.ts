import type { PermissionClaim } from "../constants/permissionClaims";
import type { SystemRole } from "../constants/systemRoles";
import { ProjectRole } from "../constants/ProjectRole";
import { ProjectPermissionUtils } from "./permissionUtils";
import { SystemRoleUtils } from "./systemRoleUtils";
import {
   AccessLevel,
   type ProjectFeature,
   type ProjectModel
} from "@kontext-tech/schema";
import type { PermissionProps } from "../permissionTypes";

export interface PermissionCheckOptions extends PermissionProps {
   requiredFeatures?: ProjectFeature[];
}

export interface PermissionEvaluationContext {
   isAuthenticated: boolean;
   project?: ProjectModel | null;
   userId?: string;
   userSystemRoles: SystemRole[];
   userPermissionClaims: PermissionClaim[];
   userProjectRoles: ProjectRole[];
   ownerId?: string;
}

export const allowsUnauthenticatedProjectRoleAccess = (
   project?: ProjectModel | null,
   allowedProjectRoles?: ProjectRole[]
): boolean => {
   if (!project || project.accessLevel !== AccessLevel.Public) {
      return false;
   }

   if (!allowedProjectRoles || allowedProjectRoles.length === 0) {
      return true;
   }

   return allowedProjectRoles.includes(ProjectRole.READER);
};

export const allowsUnauthenticatedAccess = (
   options: PermissionCheckOptions,
   project?: ProjectModel | null
): boolean => {
   if (
      options.allowedSystemRoles?.length ||
      options.allowedPermissionClaims?.length ||
      options.allowedUserIds?.length ||
      options.allowOnlyOwner
   ) {
      return false;
   }

   return allowsUnauthenticatedProjectRoleAccess(
      project,
      options.allowedProjectRoles
   );
};

export const shouldRequireAuthentication = (
   options: PermissionCheckOptions,
   project?: ProjectModel | null
): boolean => {
   return (
      options.requireAuthenticated ??
      !allowsUnauthenticatedAccess(options, project)
   );
};

export const evaluateRequiredFeatures = (
   requiredFeatures: ProjectFeature[] = [],
   project?: ProjectModel | null
): boolean => {
   if (requiredFeatures.length === 0) {
      return true;
   }

   if (!project?.configuration?.features) {
      return false;
   }

   return requiredFeatures.every((feature) =>
      project.configuration?.features?.includes(feature)
   );
};

export const evaluateProjectRoles = (
   allowedProjectRoles: ProjectRole[] = [],
   project?: ProjectModel | null,
   userProjectRoles: ProjectRole[] = []
): boolean => {
   if (!project?.id) {
      return false;
   }

   if (allowsUnauthenticatedProjectRoleAccess(project, allowedProjectRoles)) {
      return true;
   }

   if (allowedProjectRoles.length === 0) {
      return userProjectRoles.length > 0;
   }

   return allowedProjectRoles.some((role) => userProjectRoles.includes(role));
};

export const evaluateSystemRoles = (
   allowedSystemRoles: SystemRole[] = [],
   userSystemRoles: SystemRole[] = []
): boolean => {
   if (allowedSystemRoles.length === 0) {
      return false;
   }

   return SystemRoleUtils.hasAnyRole(userSystemRoles, allowedSystemRoles);
};

export const evaluatePermissionClaims = (
   allowedPermissionClaims: PermissionClaim[] = [],
   userPermissionClaims: PermissionClaim[] = [],
   userProjectRoles: ProjectRole[] = []
): boolean => {
   if (allowedPermissionClaims.length === 0) {
      return false;
   }

   if (
      allowedPermissionClaims.some((claim) =>
         userPermissionClaims.includes(claim)
      )
   ) {
      return true;
   }

   if (userProjectRoles.length === 0) {
      return false;
   }

   return allowedPermissionClaims.some((claim) =>
      ProjectPermissionUtils.hasPermission(claim, userProjectRoles)
   );
};

export const evaluateExplicitUserAccess = (
   userId?: string,
   allowedUserIds?: string[],
   ownerId?: string
): boolean => {
   if (!userId) {
      return false;
   }

   if (allowedUserIds?.includes(userId)) {
      return true;
   }

   return !!ownerId && ownerId === userId;
};

export const evaluatePermission = (
   options: PermissionCheckOptions,
   context: PermissionEvaluationContext
): boolean => {
   const requiresAuthentication = shouldRequireAuthentication(
      options,
      context.project
   );

   if (requiresAuthentication && !context.isAuthenticated) {
      return false;
   }

   if (
      options.requiredFeatures?.length &&
      !evaluateRequiredFeatures(options.requiredFeatures, context.project)
   ) {
      return false;
   }

   if (options.allowOnlyOwner) {
      return evaluateExplicitUserAccess(
         context.userId,
         options.allowedUserIds,
         context.ownerId
      );
   }

   const hasProjectRoleCriteria = !!options.allowedProjectRoles?.length;
   const hasSystemRoleCriteria = !!options.allowedSystemRoles?.length;
   const hasPermissionClaimCriteria = !!options.allowedPermissionClaims?.length;
   const hasUserIdCriteria = !!options.allowedUserIds?.length;

   if (
      !hasProjectRoleCriteria &&
      !hasSystemRoleCriteria &&
      !hasPermissionClaimCriteria &&
      !hasUserIdCriteria
   ) {
      return !requiresAuthentication || context.isAuthenticated;
   }

   return (
      (hasProjectRoleCriteria &&
         evaluateProjectRoles(
            options.allowedProjectRoles,
            context.project,
            context.userProjectRoles
         )) ||
      (hasSystemRoleCriteria &&
         evaluateSystemRoles(
            options.allowedSystemRoles,
            context.userSystemRoles
         )) ||
      (hasPermissionClaimCriteria &&
         evaluatePermissionClaims(
            options.allowedPermissionClaims,
            context.userPermissionClaims,
            context.userProjectRoles
         )) ||
      (hasUserIdCriteria &&
         evaluateExplicitUserAccess(
            context.userId,
            options.allowedUserIds,
            context.ownerId
         ))
   );
};
