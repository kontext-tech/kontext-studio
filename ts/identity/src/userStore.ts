import { logger } from "@kontext-labs/common";
import { AuthService } from "@kontext-labs/auth";
import { ServiceContainer } from "@kontext-labs/common/container";
import { setAuthAccessToken } from "@kontext-labs/common/stores";
import type { ApiErrorResult } from "@kontext-labs/common/types";
import { isLocalMode } from "@kontext-labs/common/utils";
import type {
   AccessTokenResponse,
   LoginRequest,
   UserWithRolesModel
} from "@kontext-labs/schema";
import { create } from "zustand";
import { persist } from "zustand/middleware";
import { IdentityService } from "./IdentityService";

const userServiceContainer = new ServiceContainer();

function getIdentityService(
   accessToken?: string,
   errorHandler?: (error: ApiErrorResult) => Promise<void>
) {
   userServiceContainer.setAuthContext({ accessToken });
   userServiceContainer.setErrorHandler(errorHandler);

   return userServiceContainer.getOrCreate("identity-service", (container) => {
      return new IdentityService(
         container.createAuthContext(),
         container.getErrorHandler()
      );
   });
}

function getAuthService(
   accessToken?: string,
   errorHandler?: (error: ApiErrorResult) => Promise<void>
) {
   userServiceContainer.setAuthContext({ accessToken });
   userServiceContainer.setErrorHandler(errorHandler);

   return userServiceContainer.getOrCreate("auth-service", (container) => {
      return new AuthService(
         container.createAuthContext(),
         container.getErrorHandler()
      );
   });
}

export interface PendingLoginRequest {
   request: LoginRequest;
   captchaCode?: string;
   captchaHash?: string | null;
}

export interface UserState {
   user: UserWithRolesModel | null;
   tokens: AccessTokenResponse | null;
   isLoading: boolean;
   pendingLoginRequest: PendingLoginRequest | null;
   isAuthenticated: boolean;
   login: (
      loginRequest: LoginRequest,
      captchaCode?: string,
      captchaHash?: string | null,
      errorCallback?: (errorResult: ApiErrorResult) => Promise<void>
   ) => Promise<boolean>;
   refreshTokens: () => Promise<boolean>;
   logoff: () => Promise<void>;
   clearStore: () => void;
   updateUser: (updatedUser: UserWithRolesModel) => void;
   setPendingLoginRequest: (pendingRequest: PendingLoginRequest | null) => void;
   getUserRolesForProject: (projectId: string) => string[];
   hasProjectRole: (projectId: string, role: string) => boolean;
   hasAnyProjectRole: (projectId: string, roles: string[]) => boolean;
   setUser: (user: UserWithRolesModel | null) => void;
   setTokens: (tokens: AccessTokenResponse | null) => void;
   setIsLoading: (isLoading: boolean) => void;
   fetchUser: (
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) => Promise<boolean>;
   bootstrapHostAuth: (
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) => Promise<boolean>;
}

const computeIsAuthenticated = (
   user: UserWithRolesModel | null,
   tokens: AccessTokenResponse | null
): boolean => {
   return !!user && !!tokens;
};

export const useUserStore = create<UserState>()(
   persist(
      (set, get) => ({
         user: null,
         tokens: null,
         isLoading: true,
         pendingLoginRequest: null,
         isAuthenticated: false,

         setUser: (user) => {
            const state = get();
            const isAuthenticated = computeIsAuthenticated(user, state.tokens);
            set({ user, isAuthenticated });
         },

         setTokens: (tokens) => {
            const state = get();
            const isAuthenticated = computeIsAuthenticated(state.user, tokens);
            setAuthAccessToken(tokens?.accessToken);
            set({ tokens, isAuthenticated });
         },

         setIsLoading: (isLoading) => set({ isLoading }),

         updateUser: (updatedUser) => {
            const state = get();
            const isAuthenticated = computeIsAuthenticated(
               updatedUser,
               state.tokens
            );

            const newState: Partial<UserState> = {
               user: updatedUser,
               isAuthenticated
            };
            set(newState);
         },

         setPendingLoginRequest: (pendingRequest) =>
            set({ pendingLoginRequest: pendingRequest }),

         clearStore: () => {
            setAuthAccessToken(undefined);
            set({
               user: null,
               tokens: null,
               isLoading: false,
               isAuthenticated: false,
               pendingLoginRequest: null
            });
            logger.debug("[UserStore] Store cleared completely");
         },

         getUserRolesForProject: (projectId: string) => {
            const state = get();
            return state.user?.projectRoles?.[projectId] ?? [];
         },

         hasProjectRole: (projectId: string, role: string) => {
            return get().getUserRolesForProject(projectId).includes(role);
         },

         hasAnyProjectRole: (projectId: string, roles: string[]) => {
            const userRoles = get().getUserRolesForProject(projectId);
            return roles.some((role) => userRoles.includes(role));
         },

         fetchUser: async (errorHandler) => {
            const state = get();
            logger.debug("[UserStore] Starting fetchUser...");
            set({ isLoading: true });

            try {
               const userResult = await getIdentityService(
                  state.tokens?.accessToken,
                  errorHandler
               ).getCurrentUser();
               if (userResult.succeed && userResult.data) {
                  const isAuthenticated = computeIsAuthenticated(
                     userResult.data,
                     state.tokens
                  );

                  set({
                     user: userResult.data,
                     isLoading: false,
                     isAuthenticated
                  });

                  return true;
               }

               console.error("Failed to fetch user:", userResult.error);
               set({
                  user: null,
                  isLoading: false,
                  isAuthenticated: false
               });
               return false;
            } catch (error) {
               console.error("[UserStore] fetchUser error:", error);
               set({
                  user: null,
                  isLoading: false,
                  isAuthenticated: false
               });
               return false;
            }
         },

         bootstrapHostAuth: async (errorHandler) => {
            set({ isLoading: true });

            const result = await getAuthService(
               undefined,
               errorHandler
            ).bootstrap();

            if (!result.succeed) {
               set({
                  tokens: null,
                  user: null,
                  isLoading: false,
                  isAuthenticated: false
               });
               return false;
            }

            if (!result.data) {
               set({ isLoading: false });
               return false;
            }

            get().setTokens(result.data);
            return get().fetchUser(errorHandler);
         },

         login: async (
            loginRequest,
            captchaCode,
            captchaHash,
            errorCallback
         ) => {
            const state = get();
            set({ isLoading: true });

            const result = await getAuthService(
               state.tokens?.accessToken,
               errorCallback
            ).login(loginRequest, captchaCode, captchaHash || undefined);

            if (result.succeed) {
               get().setTokens(result.data!);
               set({ isLoading: false });
               return get().fetchUser();
            }

            if (result.error?.isTwoFactorRequired) {
               set({
                  pendingLoginRequest: {
                     request: loginRequest,
                     captchaCode,
                     captchaHash
                  },
                  isLoading: false
               });
               return false;
            }

            set({
               tokens: null,
               user: null,
               isLoading: false,
               isAuthenticated: false
            });
            return false;
         },

         refreshTokens: async () => {
            const state = get();
            if (!state.tokens?.refreshToken) return false;

            logger.debug("[UserStore] Starting token refresh...");
            set({ isLoading: true });

            try {
               const result = await getAuthService(
                  state.tokens?.accessToken
               ).refreshToken(
                  state.tokens.refreshToken,
                  async (errorResult: ApiErrorResult) => {
                     console.error("Token refresh failed:", errorResult);
                  }
               );

               if (!result.succeed) {
                  logger.debug(
                     "[UserStore] Token refresh failed, clearing auth state"
                  );
                  set({ tokens: null, user: null, isAuthenticated: false });
                  return false;
               }

               const newTokens = result.data!;
               const isAuthenticated = computeIsAuthenticated(
                  state.user,
                  newTokens
               );
               logger.debug(
                  "[UserStore] Token refresh successful, updating tokens"
               );
               set({ tokens: newTokens, isAuthenticated });

               logger.debug(
                  "[UserStore] Fetching fresh user data after token refresh..."
               );
               const fetchSuccess = await get().fetchUser();
               logger.debug(
                  "[UserStore] Token refresh and user fetch complete, success:",
                  fetchSuccess
               );
               return fetchSuccess;
            } finally {
               set({ isLoading: false });
            }
         },

         logoff: async () => {
            const state = get();
            set({ isLoading: true });

            try {
               await getAuthService(state.tokens?.accessToken).logout();
               logger.debug("[UserStore] Logout completed");
            } catch (error) {
               console.error("Logout error:", error);
            } finally {
               get().clearStore();
            }
         }
      }),
      {
         name: "user-storage",
         partialize: (state) => ({
            user: state.user,
            // Local JWTs stay in memory: the launch token in sessionStorage
            // re-mints them on reload, so they never need long-lived storage.
            tokens: isLocalMode() ? null : state.tokens
         }),
         onRehydrateStorage: () => (state) => {
            if (state) {
               if (isLocalMode()) {
                  setAuthAccessToken(undefined);
                  state.setTokens(null);
                  state.setUser(null);
                  state.setIsLoading(true);

                  void state
                     .bootstrapHostAuth()
                     .then((bootstrapSuccess) => {
                        if (bootstrapSuccess) {
                           logger.debug(
                              "[UserStore] Local host auth bootstrapped successfully"
                           );
                        } else {
                           state.setIsLoading(false);
                        }
                     })
                     .catch((error) => {
                        console.error(
                           "[UserStore] Local host auth bootstrap failed:",
                           error
                        );
                        state.setIsLoading(false);
                     });
                  return;
               }

               setAuthAccessToken(state.tokens?.accessToken);
               state.isAuthenticated = computeIsAuthenticated(
                  state.user,
                  state.tokens
               );

               if (state.tokens) {
                  state.setIsLoading(true);

                  const attemptTokenRefresh = (context: string): void => {
                     void state
                        .refreshTokens()
                        .then((refreshSuccess) => {
                           if (refreshSuccess) {
                              logger.debug(
                                 `[UserStore] Session reinstated successfully after token refresh (${context})`
                              );
                           } else {
                              logger.debug(
                                 `[UserStore] Token refresh failed (${context}) - both tokens are invalid, user will need to re-authenticate`
                              );
                              state.setIsLoading(false);
                           }
                        })
                        .catch((refreshError) => {
                           console.error(
                              `[UserStore] Unexpected error during token refresh (${context}):`,
                              refreshError
                           );
                           state.setIsLoading(false);
                        });
                  };

                  void getIdentityService(state.tokens.accessToken)
                     .getCurrentUser()
                     .then((userResult) => {
                        if (userResult.succeed && userResult.data) {
                           state.updateUser(userResult.data);
                           state.setIsLoading(false);
                           logger.debug(
                              "[UserStore] Session reinstated successfully using existing access token"
                           );
                        } else {
                           logger.debug(
                              "[UserStore] User fetch failed, attempting token refresh..."
                           );
                           attemptTokenRefresh("after user fetch failure");
                        }
                     })
                     .catch((error) => {
                        logger.debug(
                           "[UserStore] User fetch error on startup, attempting token refresh...",
                           error
                        );
                        attemptTokenRefresh("after user fetch error");
                     });
               } else {
                  state.setIsLoading(false);
               }
            }
         }
      }
   )
);
