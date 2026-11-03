import {
   ApiBaseService,
   HttpApiService,
   DataApiBaseService,
   useAuthContextStore
} from "@kontext-labs/common";
import type {
   ApiAuthContext,
   ApiErrorResult
} from "@kontext-labs/common/types";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { useOptionalDefaultServiceErrorHandler } from "../context";

function useStableErrorHandler(
   errorHandler?: (errorResult: ApiErrorResult) => Promise<void>
) {
   const errorHandlerRef = useRef(errorHandler);

   useEffect(() => {
      errorHandlerRef.current = errorHandler;
   }, [errorHandler]);

   return useCallback(async (errorResult: ApiErrorResult) => {
      await errorHandlerRef.current?.(errorResult);
   }, []);
}

type ServiceBase = ApiBaseService | HttpApiService;

export function useService<TService extends ServiceBase>(
   ServiceClass: new (
      authContext: ApiAuthContext,
      errorHandler?: (errorResult: ApiErrorResult) => Promise<void>,
      basePath?: string
   ) => TService,
   errorHandler?: (errorResult: ApiErrorResult) => Promise<void>,
   basePath?: string
): TService {
   const accessToken = useAuthContextStore(
      (state: { accessToken?: string }) => state.accessToken
   );
   const defaultErrorHandler = useOptionalDefaultServiceErrorHandler();
   const stableErrorHandler = useStableErrorHandler(
      errorHandler ?? defaultErrorHandler
   );

   return useMemo(() => {
      const authContext: ApiAuthContext = {
         accessToken
      };

      return new ServiceClass(authContext, stableErrorHandler, basePath);
   }, [ServiceClass, accessToken, basePath, stableErrorHandler]);
}

export function useDataService<TService extends DataApiBaseService>(
   ServiceClass: new (
      authContext: ApiAuthContext,
      errorHandler?: (errorResult: ApiErrorResult) => Promise<void>
   ) => TService,
   errorHandler?: (errorResult: ApiErrorResult) => Promise<void>
): TService {
   const accessToken = useAuthContextStore(
      (state: { accessToken?: string }) => state.accessToken
   );
   const defaultErrorHandler = useOptionalDefaultServiceErrorHandler();
   const stableErrorHandler = useStableErrorHandler(
      errorHandler ?? defaultErrorHandler
   );

   return useMemo(() => {
      const authContext: ApiAuthContext = {
         accessToken
      };

      return new ServiceClass(authContext, stableErrorHandler);
   }, [ServiceClass, accessToken, stableErrorHandler]);
}
