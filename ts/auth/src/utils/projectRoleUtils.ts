import { ProjectRole } from "../constants/ProjectRole";

/**
 * Common role groups used throughout the application
 */
export const CommonRoleGroups = {
   // All authenticated users
   ALL_USERS: [
      ProjectRole.READER,
      ProjectRole.CONTRIBUTOR,
      ProjectRole.ADMIN,
      ProjectRole.OWNER
   ],

   // Users who can edit content
   CONTENT_EDITORS: [
      ProjectRole.CONTRIBUTOR,
      ProjectRole.ADMIN,
      ProjectRole.OWNER
   ],

   // Users who can manage the project
   PROJECT_MANAGERS: [ProjectRole.ADMIN, ProjectRole.OWNER]
};

/**
 * Utility functions for working with project roles
 */
export const ProjectRoleUtils = {
   /**
    * Gets the claim type string for a specific role
    * Mirrors the backend GetClaimType method
    */
   getClaimType: (role: ProjectRole): string => {
      return `project.${role}`;
   },

   /**
    * Returns all available project roles
    */
   getAllRoles: (): ProjectRole[] => {
      return [...CommonRoleGroups.ALL_USERS];
   },

   /**
    * Gets an array of roles that can edit content
    */
   getContentEditingRoles: (): ProjectRole[] => {
      return [...CommonRoleGroups.CONTENT_EDITORS];
   },

   /**
    * Gets an array of roles that can manage the project
    */
   getProjectManagementRoles: (): ProjectRole[] => {
      return [...CommonRoleGroups.PROJECT_MANAGERS];
   }
};
