import type { PermissionClaim } from "../constants/permissionClaims";
import type { SystemRole } from "../constants/systemRoles";
import { LoadingSpinner } from "@kontext-labs/ui";
import { Flex, Result } from "antd";
import type { ReactNode } from "react";
import { usePermissionContext } from "../context/PermissionContext";
import AuthenticatedRoute from "./AuthenticatedRoute";

interface ProtectedRouteProps {
   children: ReactNode;
   /** Path to redirect to for unauthenticated users */
   loginPath?: string;
   allowedSystemRoles?: SystemRole[];
   allowedPermissionClaims?: PermissionClaim[];
}

const ProtectedRoute = ({
   children,
   loginPath = "/login",
   allowedSystemRoles,
   allowedPermissionClaims
}: ProtectedRouteProps) => {
   const { isLoading, isAdministrator, hasSystemRole, hasPermissionClaim } =
      usePermissionContext();

   if (isLoading) {
      return <LoadingSpinner />;
   }

   if (allowedSystemRoles && allowedSystemRoles.length > 0) {
      if (!hasSystemRole(allowedSystemRoles)) {
         return (
            <Flex justify="center" align="center" style={{ padding: "48px" }}>
               <Result
                  status="403"
                  title="Access Denied"
                  subTitle="You do not have permission to view this page."
               />
            </Flex>
         );
      }
   }

   if (allowedPermissionClaims && allowedPermissionClaims.length > 0) {
      if (!isAdministrator() && !hasPermissionClaim(allowedPermissionClaims)) {
         return (
            <Flex justify="center" align="center" style={{ padding: "48px" }}>
               <Result
                  status="403"
                  title="Access Denied"
                  subTitle="You do not have the required permissions to view this page."
               />
            </Flex>
         );
      }
   }

   return (
      <AuthenticatedRoute loginPath={loginPath}>{children}</AuthenticatedRoute>
   );
};

export default ProtectedRoute;
