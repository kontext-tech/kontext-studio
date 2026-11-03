import { useRoute } from "@/hooks/useRoute";
import { RouteNames } from "@/types";
import { createApiErrorHandler } from "@kontext-tech/auth";
import type { ApiErrorResult } from "@kontext-tech/common";
import { useUserStore } from "@kontext-tech/identity";
import { useUiApp } from "@kontext-tech/ui";
import { useCallback, useEffect, useRef, useState } from "react";

export const useApiErrorHandler = () => {
   const { modal, message } = useUiApp();
   const { getGeneralRoutePath } = useRoute();
   const [sessionModalShown, setSessionModalShown] = useState(false);

   // Rebuild the concrete handler when its inputs change, but expose a
   // referentially stable wrapper. Consumers put this handler in effect
   // dependency arrays; an unstable identity there causes repeated fetches.
   // The concrete handler is constructed inside an effect (never during
   // render) so it is safe to close over the latest values.
   const handlerRef = useRef<(errorResult: ApiErrorResult) => Promise<void>>(
      async () => undefined
   );

   useEffect(() => {
      handlerRef.current = createApiErrorHandler({
         getLoginPath: () => getGeneralRoutePath(RouteNames.LOGIN),
         isSessionModalShown: () => sessionModalShown,
         setSessionModalShown,
         onUnauthorized: async ({
            errorResult,
            currentLocation,
            loginPath,
            redirectUrl,
            markResolved
         }) => {
            const errorMessage = errorResult.messages.join(" ");
            const currentPath = currentLocation.pathname;

            if (currentPath === loginPath) {
               markResolved();
               modal.error({
                  title: errorResult.title,
                  content: errorMessage
               });
               return;
            }

            const userStore = useUserStore.getState();
            const { isAuthenticated, refreshTokens, clearStore } = userStore;

            if (errorResult.isReauthRequired) {
               clearStore();
               markResolved();
               window.location.assign(redirectUrl);
               return;
            }

            if (!isAuthenticated) {
               markResolved();
               window.location.assign(redirectUrl);
               return;
            }

            modal.confirm({
               title: "Session Expired",
               content:
                  "Your session has expired. Would you like to refresh your session?",
               maskClosable: false,
               closable: false,
               okText: "Refresh Session",
               cancelButtonProps: { style: { display: "none" } },
               onOk: async () => {
                  try {
                     const refreshSuccess = await refreshTokens();

                     if (!refreshSuccess) {
                        throw new Error("Refresh failed");
                     }

                     message.success("Session refreshed successfully");
                     markResolved();
                  } catch (error) {
                     console.error("Error during token refresh:", error);
                     modal.error({
                        title: "Session Refresh Failed",
                        content:
                           "An error occurred while refreshing your session or it expired completely.",
                        maskClosable: false,
                        closable: false,
                        okText: "Sign In",
                        onOk: () => {
                           clearStore();
                           markResolved();
                           window.location.assign(redirectUrl);
                        },
                        afterClose: markResolved
                     });
                  }
               },
               afterClose: markResolved
            });
         },
         onError: async (errorMessage, errorResult) => {
            modal.error({
               title: errorResult.title,
               content: errorMessage
            });
         }
      });
   }, [getGeneralRoutePath, message, modal, sessionModalShown]);

   return useCallback(
      (errorResult: ApiErrorResult) => handlerRef.current(errorResult),
      []
   );
};
