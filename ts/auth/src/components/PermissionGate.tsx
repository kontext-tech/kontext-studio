import type { PermissionProps } from "../permissionTypes";
import { LoadingSpinner } from "@kontext-labs/ui";
import type { ReactNode } from "react";
import { useMemo } from "react";
import { usePermissionContext } from "../context/PermissionContext";

interface PermissionGateProps extends PermissionProps {
   children: ReactNode;
   fallback?: ReactNode;
   loadingFallback?: ReactNode;
}

const PermissionGate = ({
   children,
   fallback = null,
   loadingFallback = <LoadingSpinner />,
   allowedProjectRoles,
   allowedSystemRoles,
   allowedPermissionClaims,
   requireAuthenticated = false,
   allowedUserIds,
   allowOnlyOwner = false
}: PermissionGateProps) => {
   const { hasPermission, isLoading } = usePermissionContext();
   const hasAccess = useMemo(() => {
      if (isLoading) {
         return null;
      }

      return hasPermission({
         allowedProjectRoles,
         allowedSystemRoles,
         allowedPermissionClaims,
         allowedUserIds,
         requireAuthenticated,
         allowOnlyOwner
      });
   }, [
      hasPermission,
      isLoading,
      allowedProjectRoles,
      allowedSystemRoles,
      allowedPermissionClaims,
      allowedUserIds,
      requireAuthenticated,
      allowOnlyOwner
   ]);

   if (hasAccess === null || isLoading) {
      return <>{loadingFallback}</>;
   }

   if (hasAccess) {
      return <>{children}</>;
   }

   return <>{fallback}</>;
};

export default PermissionGate;
