/**
 * API response and error types used across Kontext
 */

/**
 * Authentication context for API services
 */
export interface ApiAuthContext {
   accessToken?: string;
}

/**
 * Detailed error result with various error type indicators
 */
export interface ApiErrorResult {
   title: string;
   status: number;
   messages: string[];
   error?: unknown;
   isCaptchaError?: boolean;
   isTwoFactorRequired?: boolean;
   isAccountNotActivated?: boolean;
   isAuthError?: boolean;
   isReauthRequired?: boolean;
}

/**
 * Generic API result wrapper for all API operations
 * Provides consistent success/failure handling across the platform
 */
export class ApiResult<T> {
   succeed: boolean;
   data?: T;
   error?: ApiErrorResult;

   constructor(succeed: boolean, data?: T, error?: ApiErrorResult) {
      this.succeed = succeed;
      this.data = data;
      this.error = error;
   }

   /**
    * Create a successful API result
    */
   static success<T>(data: T): ApiResult<T> {
      return new ApiResult(true, data);
   }

   /**
    * Create a failed API result
    */
   static failure<T>(error: ApiErrorResult): ApiResult<T> {
      return new ApiResult(false, null as T, error);
   }
}
