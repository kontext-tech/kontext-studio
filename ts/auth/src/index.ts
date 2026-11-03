// Context & hook
export {
   PermissionContext,
   usePermissionContext
} from "./context/PermissionContext";
export type { PermissionContextValue } from "./context/PermissionContext";
export {
   createPermissionContextValue,
   createPermissionProvider,
   type ResolvedPermissionProviderState,
   type ResolvedRoutePermission
} from "./context/CreatePermissionProvider";

// Components
export { default as AuthenticatedRoute } from "./components/AuthenticatedRoute";
export { default as AccessDeniedAlert } from "./components/AccessDeniedAlert";
export type { AccessDeniedAlertProps } from "./components/AccessDeniedAlert";
export { default as PermissionButton } from "./components/PermissionButton";
export { default as PermissionGate } from "./components/PermissionGate";
export { default as PermissionSearch } from "./components/PermissionSearch";
export type { PermissionSearchProps } from "./components/PermissionSearch";
export { default as PermissionSelect } from "./components/PermissionSelect";
export type { PermissionSelectProps } from "./components/PermissionSelect";
export { default as ProtectedRoute } from "./components/ProtectedRoute";
export { default as ProjectRoleTag } from "./components/ProjectRoleTag";
export type { ProjectRoleTagProps } from "./components/ProjectRoleTag";
export { default as ProjectRoleTags } from "./components/ProjectRoleTags";
export type { ProjectRoleTagsProps } from "./components/ProjectRoleTags";
export { default as SignInButton } from "./components/SignInButton";
export type { SignInButtonProps } from "./components/SignInButton";

// Types
export type { PermissionProps } from "./permissionTypes";

// Utils
export {
   allowsUnauthenticatedAccess,
   allowsUnauthenticatedProjectRoleAccess,
   evaluateExplicitUserAccess,
   evaluatePermission,
   evaluatePermissionClaims,
   evaluateProjectRoles,
   evaluateRequiredFeatures,
   evaluateSystemRoles,
   shouldRequireAuthentication,
   type PermissionCheckOptions,
   type PermissionEvaluationContext
} from "./utils/permissionEvaluator";
export { ProjectPermissionUtils } from "./utils/permissionUtils";

export * from "./AuthService";
export * from "./constants/queryParams";
export * from "./constants/permissionClaims";
export * from "./constants/systemRoles";
export * from "./constants/ProjectRole";
export * from "./utils/navigationUtils";
export * from "./utils/projectRoleUtils";
export * from "./utils/systemRoleUtils";
export * from "./utils/createApiErrorHandler";
