import type { Client, ClientOptions } from "openapi-fetch";
import createClient from "openapi-fetch";
import type { paths } from "@kontext-labs/schema/api";
import type { ApiAuthContext, ApiErrorResult } from "../types";
import {
   ApiRequestError,
   normalizeApiError,
   parseApiErrorPayload
} from "../utils/apiError";
import { API_BASE_PATH } from "../utils/envUtils";

/** Typed openapi-fetch client shared by every API service. */
type ApiClient = Client<paths>;

/**
 * Result returned by openapi-fetch. Declared structurally so services can pass
 * the promise straight to {@link ApiBaseService.request} without importing
 * the helper types from openapi-fetch.
 */
interface ApiResponse<T> {
   data?: T;
   error?: unknown;
   response: Response;
}

/**
 * Base class for all API services
 * Provides common error handling functionality and manages API client lifecycle
 */
export abstract class ApiBaseService {
   protected errorHandler?: (error: ApiErrorResult) => Promise<void>;
   protected apiClient: ApiClient;
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

      // Create initial API client
      this.apiClient = this.createApiClient();
   }

   /**
    * Creates a new API client with current auth context.
    */
   protected createApiClient(): ApiClient {
      return createClient<paths>(this.getApiClientConfiguration());
   }

   /**
    * Prepares the configuration object for API client creation.
    * Contains common logic for auth, headers, and request setup.
    */
   protected getApiClientConfiguration(): ClientOptions {
      // Determine if we're making cross-origin requests (when using API subdomain)
      const isAbsoluteUrl = API_BASE_PATH.startsWith("http");
      const credentials: RequestCredentials = isAbsoluteUrl
         ? "include"
         : "same-origin";

      // Base headers object - we'll add Origin for cross-origin requests
      const baseHeaders: Record<string, string> = {};

      // Add authorization header if using access token
      if (this.currentAuthContext.accessToken) {
         baseHeaders.Authorization = `Bearer ${this.currentAuthContext.accessToken}`;
      }

      // For cross-origin requests with credentials, explicitly set Origin header
      // This ensures CORS headers are consistently applied by nginx
      if (
         credentials === "include" &&
         isAbsoluteUrl &&
         typeof window !== "undefined"
      ) {
         baseHeaders.Origin = window.location.origin;
      }

      return {
         baseUrl: this.customBasePath || API_BASE_PATH,
         credentials,
         headers: baseHeaders
      };
   }

   /**
    * Unwraps an openapi-fetch result into its success payload.
    *
    * openapi-fetch reports HTTP failures in `error` instead of throwing. The
    * transport normalizes that payload into an {@link ApiRequestError}, so
    * services can keep using try/catch and the shared error handler.
    */
   protected async request<T>(call: Promise<ApiResponse<T>>): Promise<T> {
      return (await this.requestResponse(call)).data;
   }

   /**
    * Like {@link request}, but also returns the raw response for callers that
    * need response headers (e.g. `Location` on uploads).
    */
   protected async requestResponse<T>(
      call: Promise<ApiResponse<T>>
   ): Promise<{ data: T; response: Response }> {
      const { data, error, response } = await call;
      if (error !== undefined || !response.ok) {
         throw new ApiRequestError(
            parseApiErrorPayload({
               status: response.status,
               statusText: response.statusText,
               body: error
            })
         );
      }
      return { data: data as T, response };
   }

   protected handleApiError = async (
      error: unknown
   ): Promise<ApiErrorResult> => {
      const errorResult = await this.parseApiError(error);
      await this.errorHandler?.(errorResult);
      return errorResult;
   };

   /**
    * Parse an error without raising the global error UI for ordinary failures.
    *
    * Used by callers that render the failure inline (e.g. Python execution
    * shown in a tool-call card or notebook block). Auth/reauth failures still
    * go through the injected handler so session recovery keeps working.
    */
   protected handleInlineApiError = async (
      error: unknown
   ): Promise<ApiErrorResult> => {
      const errorResult = await this.parseApiError(error);
      if (errorResult.isAuthError || errorResult.isReauthRequired) {
         await this.errorHandler?.(errorResult);
      }
      return errorResult;
   };

   protected parseApiError = normalizeApiError;

   /** HTTP status carried by a normalized request error, if any. */
   protected getErrorStatus(error: unknown): number | undefined {
      return error instanceof ApiRequestError ? error.result.status : undefined;
   }

   /**
    * Updates the authentication context and recreates the API client.
    * Call this when auth tokens are refreshed to ensure the service uses new credentials.
    */
   public updateAuthContext(authContext: ApiAuthContext): void {
      this.currentAuthContext = { ...authContext };
      this.apiClient = this.createApiClient();
   }

   /**
    * Updates the global error handler for the service.
    */
   public setErrorHandler(
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ): void {
      this.errorHandler = errorHandler;
   }
}
