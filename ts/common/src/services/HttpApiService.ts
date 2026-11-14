import { ApiResult } from "../types";
import type { ApiAuthContext, ApiErrorResult } from "../types";
import {
   ApiRequestError,
   normalizeApiError,
   parseResponseToApiError
} from "../utils/apiError";
import { API_BASE_PATH } from "../utils/envUtils";

export abstract class HttpApiService {
   protected errorHandler?: (error: ApiErrorResult) => Promise<void>;
   protected currentAuthContext: ApiAuthContext;
   protected customBasePath?: string;

   constructor(
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>,
      customBasePath?: string
   ) {
      this.currentAuthContext = { ...authContext };
      this.errorHandler = errorHandler;
      this.customBasePath = customBasePath;
   }

   protected getApiClientConfiguration() {
      const basePath = this.customBasePath || API_BASE_PATH;
      const isAbsoluteUrl = basePath.startsWith("http");
      const credentials = isAbsoluteUrl ? "include" : "same-origin";
      const headers: Record<string, string> = {};

      if (this.currentAuthContext.accessToken) {
         headers.Authorization = `Bearer ${this.currentAuthContext.accessToken}`;
      }

      if (
         credentials === "include" &&
         isAbsoluteUrl &&
         typeof window !== "undefined"
      ) {
         headers.Origin = window.location.origin;
      }

      return { basePath, credentials, headers };
   }

   protected async requestJson<T>(
      path: string,
      init: RequestInit = {}
   ): Promise<T> {
      const config = this.getApiClientConfiguration();
      const headers = new Headers(init.headers);

      for (const [key, value] of Object.entries(config.headers)) {
         headers.set(key, value);
      }

      const response = await fetch(`${config.basePath}${path}`, {
         ...init,
         credentials:
            init.credentials ?? (config.credentials as RequestCredentials),
         headers
      });

      if (!response.ok) {
         throw new ApiRequestError(await parseResponseToApiError(response));
      }

      if (response.status === 204) {
         return undefined as T;
      }

      return (await response.json()) as T;
   }

   protected buildPath(
      path: string,
      params: Record<string, unknown | unknown[]> = {}
   ): string {
      const searchParams = new URLSearchParams();
      for (const [key, value] of Object.entries(params)) {
         if (value === undefined || value === null) continue;
         if (Array.isArray(value)) {
            value.forEach((item) => {
               if (item !== undefined && item !== null) {
                  searchParams.append(key, String(item));
               }
            });
         } else {
            searchParams.set(key, String(value));
         }
      }

      const query = searchParams.toString();
      return query ? `${path}?${query}` : path;
   }

   protected handleApiError = async (
      error: unknown
   ): Promise<ApiErrorResult> => {
      const errorResult = await this.parseApiError(error);
      await this.errorHandler?.(errorResult);
      return errorResult;
   };

   protected parseApiError = normalizeApiError;

   /**
    * Runs a request and wraps the outcome in an {@link ApiResult}, routing
    * failures through the shared error handler (raises the global error UI).
    */
   protected async wrap<T>(call: () => Promise<T>): Promise<ApiResult<T>> {
      try {
         return ApiResult.success(await call());
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   public updateAuthContext(authContext: ApiAuthContext): void {
      this.currentAuthContext = { ...authContext };
   }

   public setErrorHandler(
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ): void {
      this.errorHandler = errorHandler;
   }
}
