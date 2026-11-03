import type { ApiErrorResult } from "../types";
import { ProblemTypes } from "@kontext-tech/schema";
import { logger } from "./logger";

/**
 * Normalized error payload. `body` is already parsed when it came from
 * openapi-fetch, or is the raw text when a plain `Response` was not JSON.
 */
export interface ApiErrorPayload {
   status: number;
   statusText?: string;
   body?: unknown;
}

/**
 * Error thrown by the HTTP transports. Carrying the normalized result means
 * callers never have to re-read a response body that openapi-fetch already
 * consumed.
 */
export class ApiRequestError extends Error {
   constructor(public readonly result: ApiErrorResult) {
      super(result.title);
      this.name = "ApiRequestError";
   }
}

/** Result used when an error cannot be attributed to an HTTP response. */
export const createFallbackApiError = (): ApiErrorResult => ({
   title: "Error",
   status: 500,
   messages: ["Operation failed. Please try again."],
   isAuthError: false
});

const fallbackMessageForStatus = (
   status: number,
   statusText?: string
): string => statusText || `Request failed with HTTP ${status}`;

const isRecord = (value: unknown): value is Record<string, unknown> =>
   typeof value === "object" && value !== null;

const isEmptyBody = (body: unknown): boolean =>
   body === undefined || (typeof body === "string" && body.trim().length === 0);

interface ValidationErrorBody {
   title?: unknown;
   errors: Record<string, unknown>;
}

const isValidationErrorBody = (value: unknown): value is ValidationErrorBody =>
   isRecord(value) && isRecord(value["errors"]);

/**
 * FastAPI/Pydantic request-validation bodies carry `detail` as an *array* of
 * `{ type, loc, msg }` entries. Casting the array to a string renders the
 * infamous "[object Object]"; format each entry into `loc: msg` text instead.
 * ("body" loc segments are dropped — "file: Field required" reads better than
 * "body.file: Field required".)
 */
const isFastApiValidationDetail = (detail: unknown): detail is unknown[] =>
   Array.isArray(detail) && detail.length > 0;

const formatFastApiValidationMessages = (detail: unknown[]): string[] =>
   detail.map((entry) => {
      if (!isRecord(entry) || typeof entry["msg"] !== "string") {
         return String(entry);
      }
      const loc = Array.isArray(entry["loc"])
         ? entry["loc"].filter((part) => part !== "body").join(".")
         : undefined;
      return loc ? `${loc}: ${entry["msg"]}` : (entry["msg"] as string);
   });

/**
 * Convert an HTTP status and its error body into the UI-facing result.
 * Used by both the openapi-fetch transport and the raw `fetch` transport.
 */
export function parseApiErrorPayload({
   status,
   statusText,
   body
}: ApiErrorPayload): ApiErrorResult {
   const isAuthError = status === 401 || status === 403;

   if (isEmptyBody(body)) {
      return {
         title: `HTTP Error ${status}`,
         status,
         messages: [fallbackMessageForStatus(status, statusText)],
         isAuthError
      };
   }

   if (isValidationErrorBody(body)) {
      const messages = Object.values(body.errors).flatMap((value) =>
         Array.isArray(value)
            ? value.map((item) => String(item))
            : [String(value)]
      );
      const title =
         typeof body["title"] === "string" ? body["title"] : undefined;

      return {
         title: title || "Validation Error",
         status,
         messages,
         isCaptchaError: "CAPTCHA_INVALID" in body.errors,
         isAuthError
      };
   }

   if (isRecord(body) && ("detail" in body || "type" in body)) {
      const problemDetails = body;
      let isCaptchaError = false;
      let isTwoFactorRequired = false;

      if (problemDetails["type"] === ProblemTypes.RequiresTwoFactor) {
         isTwoFactorRequired = true;
      } else if (
         problemDetails["type"] === ProblemTypes.UnsupportedTokenVersion
      ) {
         return {
            title: "Re-authentication required",
            status: (problemDetails["status"] as number) || status,
            messages: [
               (problemDetails["detail"] as string) ||
                  "Your session is no longer valid. Please sign in again."
            ],
            isTwoFactorRequired,
            isCaptchaError,
            isAuthError: true,
            isReauthRequired: true
         };
      } else if (problemDetails["type"] === ProblemTypes.AccountNotActivated) {
         return {
            title: "Account Not Activated",
            status: (problemDetails["status"] as number) || status,
            messages: [
               (problemDetails["detail"] as string) ||
                  "Your account is not activated. Please check your email and confirm your account."
            ],
            isAccountNotActivated: true,
            isTwoFactorRequired,
            isCaptchaError,
            isAuthError: true
         };
      } else if (
         problemDetails["type"] === ProblemTypes.InvalidCaptcha ||
         problemDetails["type"] === ProblemTypes.MissingCaptcha ||
         problemDetails["type"] === ProblemTypes.InvalidCaptchaContext
      ) {
         isCaptchaError = true;
      }

      const messages = isFastApiValidationDetail(problemDetails["detail"])
         ? formatFastApiValidationMessages(problemDetails["detail"])
         : [
              (problemDetails["detail"] as string) ||
                 (problemDetails["title"] as string) ||
                 "An error occurred"
           ];

      return {
         title: (problemDetails["title"] as string) || "Error",
         status: (problemDetails["status"] as number) || status,
         messages,
         isTwoFactorRequired,
         isCaptchaError,
         isAuthError:
            problemDetails["status"] === 401 ||
            problemDetails["status"] === 403 ||
            isAuthError
      };
   }

   if (isRecord(body) && typeof body["title"] === "string") {
      return {
         title: body["title"],
         status,
         messages: [body["title"]],
         isAuthError
      };
   }

   const plainTextMessage =
      typeof body === "string" ? body.trim() : JSON.stringify(body);
   return {
      title: `HTTP Error ${status}`,
      status,
      messages: [
         plainTextMessage || fallbackMessageForStatus(status, statusText)
      ],
      isAuthError
   };
}

/**
 * Adapter for raw `fetch` transports that still have an unread `Response`.
 * openapi-fetch callers should pass its parsed `error` body straight to
 * {@link parseApiErrorPayload} instead.
 */
export async function parseResponseToApiError(
   response: Response
): Promise<ApiErrorResult> {
   const status = response.status || 500;

   try {
      const responseText = await response.text();
      let body: unknown;

      if (responseText.trim().length > 0) {
         try {
            body = JSON.parse(responseText);
         } catch {
            body = responseText;
         }
      }

      return parseApiErrorPayload({
         status,
         statusText: response.statusText,
         body
      });
   } catch (parseError) {
      logger.error(
         "[apiError] failed to read error response body:",
         parseError
      );
      return parseApiErrorPayload({
         status,
         statusText: response.statusText
      });
   }
}

const getResponseFromError = (error: unknown): Response | undefined => {
   if (typeof error !== "object" || error === null || !("response" in error)) {
      return undefined;
   }

   const response = (error as { response?: unknown }).response;
   return response instanceof Response ? response : undefined;
};

/**
 * Normalize anything caught by a service into `ApiErrorResult`.
 *
 * - `ApiRequestError` already carries the parsed openapi-fetch payload.
 * - Foreign transports (e.g. `@kontext-tech/host-api`) attach an unread
 *   `Response` to the thrown error; parse it on demand.
 * - Anything else gets the generic fallback.
 */
export async function normalizeApiError(
   error: unknown
): Promise<ApiErrorResult> {
   if (error instanceof ApiRequestError) {
      return error.result;
   }

   const response = getResponseFromError(error);
   if (response) {
      return parseResponseToApiError(response);
   }

   return createFallbackApiError();
}
