import type { ApiErrorResult } from "@kontext-labs/common";
import { createUrlWithReturnParam } from "./navigationUtils";

export interface CurrentLocationLike {
   pathname: string;
   search: string;
}

export interface UnauthorizedContext {
   errorResult: ApiErrorResult;
   currentLocation: CurrentLocationLike;
   loginPath: string;
   redirectUrl: string;
   markResolved: () => void;
}

export interface CreateApiErrorHandlerOptions {
   getLoginPath: () => string;
   isSessionModalShown: () => boolean;
   setSessionModalShown: (shown: boolean) => void;
   getCurrentLocation?: () => CurrentLocationLike;
   onUnauthorized: (context: UnauthorizedContext) => Promise<void>;
   onForbidden?: (errorResult: ApiErrorResult) => Promise<void> | void;
   onError: (
      message: string,
      errorResult: ApiErrorResult
   ) => Promise<void> | void;
}

export const createApiErrorHandler = ({
   getLoginPath,
   isSessionModalShown,
   setSessionModalShown,
   getCurrentLocation = () => ({
      pathname: window.location.pathname,
      search: window.location.search
   }),
   onUnauthorized,
   onForbidden,
   onError
}: CreateApiErrorHandlerOptions) => {
   return async (errorResult: ApiErrorResult) => {
      const currentLocation = getCurrentLocation();

      if (errorResult.status === 401) {
         if (isSessionModalShown()) {
            return;
         }

         setSessionModalShown(true);
         const loginPath = getLoginPath();
         const redirectUrl = createUrlWithReturnParam(
            loginPath,
            `${currentLocation.pathname}${currentLocation.search}` || "/"
         );

         await onUnauthorized({
            errorResult,
            currentLocation,
            loginPath,
            redirectUrl,
            markResolved: () => setSessionModalShown(false)
         });
         return;
      }

      if (errorResult.status === 403) {
         await onForbidden?.(errorResult);
         return;
      }

      const message =
         errorResult.messages?.join(" ") ||
         errorResult.title ||
         "An unexpected error occurred.";
      await onError(message, errorResult);
   };
};
