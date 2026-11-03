import type { SystemRole } from "../constants/systemRoles";
import { SYSTEM_ROLES } from "../constants/systemRoles";

/**
 * Predefined groups of system roles for common access patterns
 */
export const CommonSystemRoleGroups = {
   // Basic groups
   ADMINISTRATORS: [SYSTEM_ROLES.ADMINISTRATOR]
};

/**
 * Utility functions for working with system roles
 */
export const SystemRoleUtils = {
   /**
    * Get display name for a system role
    * @param role The system role
    * @returns A user-friendly display name for the role
    */
   getDisplayName: (role: SystemRole): string => {
      switch (role) {
         case SYSTEM_ROLES.ADMINISTRATOR:
            return "Administrator";
         default:
            return role;
      }
   },

   /**
    * Check if user has administrator privileges
    * @param userRoles The user's roles
    * @returns Boolean indicating if the user is an administrator
    */
   isAdministrator: (userRoles: SystemRole[]): boolean => {
      return userRoles.includes(SYSTEM_ROLES.ADMINISTRATOR);
   },

   /**
    * Check if user has any of the specified roles
    * @param userRoles The user's roles
    * @param requiredRoles The roles to check for
    * @returns Boolean indicating if the user has any of the required roles
    */
   hasAnyRole: (
      userRoles: SystemRole[],
      requiredRoles: SystemRole[]
   ): boolean => {
      if (
         !userRoles ||
         userRoles.length === 0 ||
         !requiredRoles ||
         requiredRoles.length === 0
      ) {
         return false;
      }
      return requiredRoles.some((role) => userRoles.includes(role));
   }
};
