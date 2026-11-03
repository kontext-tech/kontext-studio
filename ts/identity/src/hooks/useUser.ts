import { useUserStore } from "../userStore";

// Stable fallback: a selector must return the same reference for unchanged
// state, otherwise useSyncExternalStore re-renders in an infinite loop.
const EMPTY_PROJECT_ROLES: Record<string, string[]> = {};

const useUser = () => {
   const user = useUserStore((state) => state.user);
   const tokens = useUserStore((state) => state.tokens);
   const isLoading = useUserStore((state) => state.isLoading);
   const isAuthenticated = useUserStore((state) => state.isAuthenticated);
   const pendingLoginRequest = useUserStore(
      (state) => state.pendingLoginRequest
   );
   const projectRoles = useUserStore(
      (state) => state.user?.projectRoles ?? EMPTY_PROJECT_ROLES
   );
   const login = useUserStore((state) => state.login);
   const refreshTokens = useUserStore((state) => state.refreshTokens);
   const logoff = useUserStore((state) => state.logoff);
   const clearStore = useUserStore((state) => state.clearStore);
   const updateUser = useUserStore((state) => state.updateUser);
   const setPendingLoginRequest = useUserStore(
      (state) => state.setPendingLoginRequest
   );
   const fetchUser = useUserStore((state) => state.fetchUser);
   const bootstrapHostAuth = useUserStore((state) => state.bootstrapHostAuth);
   const getUserRolesForProject = useUserStore(
      (state) => state.getUserRolesForProject
   );
   const hasProjectRole = useUserStore((state) => state.hasProjectRole);
   const hasAnyProjectRole = useUserStore((state) => state.hasAnyProjectRole);

   return {
      user,
      tokens,
      isLoading,
      isAuthenticated,
      pendingLoginRequest,
      projectRoles,
      login,
      refreshTokens,
      logoff,
      clearStore,
      updateUser,
      setPendingLoginRequest,
      fetchUser,
      bootstrapHostAuth,
      getUserRolesForProject,
      hasProjectRole,
      hasAnyProjectRole
   };
};

export default useUser;
