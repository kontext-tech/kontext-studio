import type { PermissionClaim } from "../constants/permissionClaims";
import type { SystemRole } from "../constants/systemRoles";
import type { PermissionProps } from "../permissionTypes";
import type { ProjectModel } from "@kontext-tech/schema";
import { createContext, useContext } from "react";

/**
 * Shared permission context value interface.
 * Both app and app-admin provide their own PermissionProvider
 * that satisfies this interface.
 */
export interface PermissionContextValue {
   /** Evaluate a set of permission props (roles, claims, etc.) */
   hasPermission: (
      checkOptions: PermissionProps,
      /** Explicit project override; defaults to the context's current project. */
      project?: ProjectModel | null
   ) => boolean;
   /** Check if the current user is a system administrator */
   isAdministrator: () => boolean;
   /** Check if the user has at least one of the specified system roles */
   hasSystemRole: (roles: SystemRole[]) => boolean;
   /** Check if the user has at least one of the specified permission claims */
   hasPermissionClaim: (
      claims: PermissionClaim[],
      resource?: unknown
   ) => boolean;
   /** Optionally check access to an app-defined route */
   hasRoutePermission?: (routeName: string, context?: unknown) => boolean;
   /** Whether the permission state is still loading */
   isLoading: boolean;
   /** Whether the user is authenticated */
   isAuthenticated: boolean;
}

export const PermissionContext = createContext<PermissionContextValue | null>(
   null
);

export const usePermissionContext = (): PermissionContextValue => {
   const context = useContext(PermissionContext);
   if (!context) {
      throw new Error(
         "usePermissionContext must be used within a PermissionProvider"
      );
   }
   return context;
};
