import projectPermissionToRoles from "@kontext-tech/common/resources/security/project-permission-to-roles.json";

/**
 * Utility for mapping project-scoped permissions to roles.
 * Single source of truth is maintained in ts/common/src/resources/security/project-permission-to-roles.json
 */
export const ProjectPermissionUtils = {
   /**
    * Checks if a list of user roles has the required permission.
    *
    * @param permission The permission claim to check (e.g. "projects.read")
    * @param userRoles List of project roles the user has (e.g. ["owner", "admin"])
    * @returns true if any of the user roles are allowed for this permission
    */
   hasPermission: (permission: string, userRoles: string[]): boolean => {
      const allowedRoles = (
         projectPermissionToRoles as Record<string, string[]>
      )[permission];
      if (!allowedRoles) return false;

      // Standardize user roles (remove "project." prefix, handle "Project.Role:ID" format, lowercase)
      const standardizedUserRoles = userRoles.map((role) => {
         // Handle "Project.Role:ID" format or simple "Role" format
         const roleName = role.split(":")[0];
         // Remove "project." prefix and lowercase
         return roleName.toLowerCase().replace("project.", "");
      });

      return allowedRoles.some((role) =>
         standardizedUserRoles.includes(role.toLowerCase())
      );
   },

   /**
    * Gets all roles that are allowed for a specific permission.
    *
    * @param permission The permission claim
    * @returns List of allowed role names (lowercase)
    */
   getAllowedRoles: (permission: string): string[] => {
      return (
         (projectPermissionToRoles as Record<string, string[]>)[permission] ||
         []
      );
   }
};
