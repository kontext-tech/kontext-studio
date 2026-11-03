import type { ProjectRole } from "./constants/ProjectRole";
import type { PermissionClaim } from "./constants/permissionClaims";
import type { SystemRole } from "./constants/systemRoles";

export interface PermissionProps {
   allowedProjectRoles?: ProjectRole[];
   allowedSystemRoles?: SystemRole[];
   allowedPermissionClaims?: PermissionClaim[];
   requireAuthenticated?: boolean;
   tooltipWhenDisabled?: string;
   allowedUserIds?: string[];
   allowOnlyOwner?: boolean;
}
