import { usePermissionContext } from "../context/PermissionContext";
import { createUrlWithReturnParam } from "../utils/navigationUtils";
import { LoadingSpinner } from "@kontext-labs/ui";
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

interface AuthenticatedRouteProps {
   children: ReactNode;
   loginPath: string;
}

const AuthenticatedRoute = ({
   children,
   loginPath
}: AuthenticatedRouteProps) => {
   const { isAuthenticated, isLoading } = usePermissionContext();
   const location = useLocation();

   if (isLoading && !isAuthenticated) {
      return <LoadingSpinner />;
   }

   if (!isAuthenticated) {
      const currentPathWithQuery = location.pathname + location.search;
      const redirectPath = createUrlWithReturnParam(
         loginPath,
         currentPathWithQuery
      );

      return (
         <Navigate
            to={redirectPath}
            state={{ from: currentPathWithQuery }}
            replace
         />
      );
   }

   return <>{children}</>;
};

export default AuthenticatedRoute;
