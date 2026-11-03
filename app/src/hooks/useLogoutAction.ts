import { useRoute } from "@/hooks/useRoute";
import { RouteNames } from "@/types";
import { useUser } from "@kontext-labs/identity";
import { useCallback } from "react";
import { useNavigate } from "react-router-dom";

/**
 * Single logout behavior for every header/sidebar surface: end the session
 * and always land on the login route, even when the logoff call fails.
 */
export function useLogoutAction() {
   const { logoff } = useUser();
   const navigate = useNavigate();
   const { getRoutePath } = useRoute();

   return useCallback(async (): Promise<void> => {
      try {
         await logoff();
      } catch (error) {
         console.error("Logout error:", error);
      } finally {
         navigate(getRoutePath(RouteNames.LOGIN), { replace: true });
      }
   }, [logoff, navigate, getRoutePath]);
}
