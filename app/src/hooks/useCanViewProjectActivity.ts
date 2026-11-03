import { SYSTEM_ROLES } from "@kontext-labs/auth";
import { useUserStore } from "@kontext-labs/identity";
import { useIsLocalMode } from "@kontext-labs/site";

/**
 * Whether the current user may view project-level audit / monitoring views
 * (Query Session History, Activity Log).
 *
 * These views were previously nested under Project Settings and were only
 * exposed to global administrators or users in local mode. Project-level
 * roles also map to the underlying permission claims, so this hook keeps the
 * original, narrower audience while the routes remain permission-protected.
 */
export const useCanViewProjectActivity = (): boolean => {
   const user = useUserStore((state) => state.user);
   const isLocalMode = useIsLocalMode();

   return (
      isLocalMode ||
      (user?.roles?.includes(SYSTEM_ROLES.ADMINISTRATOR) ?? false)
   );
};
