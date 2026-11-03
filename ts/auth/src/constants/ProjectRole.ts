/**
 * Enum representing project roles in the application
 * Maps to the backend ProjectRoleClaim constants
 */
export enum ProjectRole {
   /**
    * Admin role - has full administrative permissions for a project
    */
   ADMIN = "admin",

   /**
    * Owner role - has ownership permissions for a project
    */
   OWNER = "owner",

   /**
    * Reader role - has read-only permissions for a project
    */
   READER = "reader",

   /**
    * Contributor role - has permissions to contribute content to a project
    */
   CONTRIBUTOR = "contributor"
}

/**
 * Colors associated with each project role for consistent styling
 * All roles now use gray for consistent and neutral styling
 */
export const PROJECT_ROLE_COLORS: Record<ProjectRole, string> = {
   [ProjectRole.OWNER]: "default",
   [ProjectRole.ADMIN]: "default",
   [ProjectRole.CONTRIBUTOR]: "default",
   [ProjectRole.READER]: "default"
};

/**
 * Options for project role filters in Select components
 */
export const PROJECT_ROLE_FILTER_OPTIONS = [
   { label: "Owner", value: ProjectRole.OWNER },
   { label: "Admin", value: ProjectRole.ADMIN },
   { label: "Contributor", value: ProjectRole.CONTRIBUTOR },
   { label: "Reader", value: ProjectRole.READER }
];

/**
 * Options for Table column filters
 */
export const PROJECT_ROLE_TABLE_FILTERS = PROJECT_ROLE_FILTER_OPTIONS.map(
   (option) => ({
      text: option.label,
      value: option.value
   })
);
