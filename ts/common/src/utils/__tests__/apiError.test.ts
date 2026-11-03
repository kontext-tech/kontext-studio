/// <reference types="jest" />

import { ProblemTypes } from "@kontext-labs/schema";
import {
   ApiRequestError,
   createFallbackApiError,
   normalizeApiError,
   parseApiErrorPayload,
   parseResponseToApiError
} from "../apiError";

describe("parseApiErrorPayload", () => {
   it("falls back to the status text when the body is empty", () => {
      expect(
         parseApiErrorPayload({ status: 503, statusText: "Unavailable" })
      ).toMatchObject({
         title: "HTTP Error 503",
         status: 503,
         messages: ["Unavailable"],
         isAuthError: false
      });
   });

   it("treats a whitespace-only body as empty", () => {
      expect(parseApiErrorPayload({ status: 500, body: "   " })).toMatchObject({
         title: "HTTP Error 500",
         messages: ["Request failed with HTTP 500"]
      });
   });

   it("flags 401 and 403 responses as auth errors", () => {
      expect(parseApiErrorPayload({ status: 401 }).isAuthError).toBe(true);
      expect(parseApiErrorPayload({ status: 403 }).isAuthError).toBe(true);
      expect(parseApiErrorPayload({ status: 422 }).isAuthError).toBe(false);
   });

   it("expands validation errors and detects invalid captchas", () => {
      expect(
         parseApiErrorPayload({
            status: 422,
            body: {
               type: "validation",
               title: "Validation Error",
               status: 422,
               errors: {
                  CAPTCHA_INVALID: ["Invalid captcha"],
                  email: ["Email is required"]
               }
            }
         })
      ).toEqual({
         title: "Validation Error",
         status: 422,
         messages: ["Invalid captcha", "Email is required"],
         isCaptchaError: true,
         isAuthError: false
      });
   });

   it("formats FastAPI detail arrays into readable messages", () => {
      // FastAPI/Pydantic request validation: detail is an array of entries;
      // the previous cast-to-string rendered "[object Object]".
      expect(
         parseApiErrorPayload({
            status: 422,
            body: {
               detail: [
                  {
                     type: "missing",
                     loc: ["body", "file"],
                     msg: "Field required",
                     input: null
                  },
                  {
                     type: "string_too_short",
                     loc: ["body", "name"],
                     msg: "String should have at least 1 character"
                  }
               ]
            }
         })
      ).toEqual({
         title: "Error",
         status: 422,
         messages: [
            "file: Field required",
            "name: String should have at least 1 character"
         ],
         isTwoFactorRequired: false,
         isCaptchaError: false,
         isAuthError: false
      });
   });

   it("marks unsupported token versions as requiring re-authentication", () => {
      expect(
         parseApiErrorPayload({
            status: 401,
            body: {
               type: ProblemTypes.UnsupportedTokenVersion,
               title: "Unauthorized",
               status: 401,
               detail: "Token version is no longer supported"
            }
         })
      ).toMatchObject({
         title: "Re-authentication required",
         status: 401,
         messages: ["Token version is no longer supported"],
         isAuthError: true,
         isReauthRequired: true
      });
   });

   it("flags inactive accounts", () => {
      expect(
         parseApiErrorPayload({
            status: 403,
            body: {
               type: ProblemTypes.AccountNotActivated,
               detail: "Activate your account"
            }
         })
      ).toMatchObject({
         title: "Account Not Activated",
         messages: ["Activate your account"],
         isAccountNotActivated: true,
         isAuthError: true
      });
   });

   it("flags two-factor and captcha problem types", () => {
      expect(
         parseApiErrorPayload({
            status: 401,
            body: {
               type: ProblemTypes.RequiresTwoFactor,
               detail: "2FA required"
            }
         }).isTwoFactorRequired
      ).toBe(true);

      expect(
         parseApiErrorPayload({
            status: 400,
            body: { type: ProblemTypes.InvalidCaptcha, detail: "Bad captcha" }
         }).isCaptchaError
      ).toBe(true);
   });

   it("uses a titled body as the message", () => {
      expect(
         parseApiErrorPayload({ status: 409, body: { title: "Conflict" } })
      ).toMatchObject({
         title: "Conflict",
         status: 409,
         messages: ["Conflict"]
      });
   });

   it("falls back to the raw body when the shape is unknown", () => {
      expect(
         parseApiErrorPayload({ status: 502, body: "upstream timeout" })
      ).toMatchObject({
         title: "HTTP Error 502",
         messages: ["upstream timeout"]
      });
   });
});

describe("parseResponseToApiError", () => {
   it("parses a JSON problem-details response", async () => {
      const response = new Response(
         JSON.stringify({ detail: "Boom", status: 400 }),
         {
            status: 400,
            statusText: "Bad Request",
            headers: { "Content-Type": "application/json" }
         }
      );

      await expect(parseResponseToApiError(response)).resolves.toMatchObject({
         title: "Error",
         status: 400,
         messages: ["Boom"]
      });
   });

   it("parses a plain-text response", async () => {
      const response = new Response("Gateway unavailable", { status: 503 });

      await expect(parseResponseToApiError(response)).resolves.toMatchObject({
         title: "HTTP Error 503",
         messages: ["Gateway unavailable"]
      });
   });
});

describe("ApiRequestError", () => {
   it("carries the normalized result", () => {
      const result = createFallbackApiError();
      const error = new ApiRequestError(result);

      expect(error.name).toBe("ApiRequestError");
      expect(error.message).toBe("Error");
      expect(error.result).toBe(result);
   });
});

describe("normalizeApiError", () => {
   it("returns the normalized result from ApiRequestError", async () => {
      const result = {
         title: "Conflict",
         status: 409,
         messages: ["Conflict"]
      };

      await expect(
         normalizeApiError(new ApiRequestError(result))
      ).resolves.toBe(result);
   });

   it("parses a foreign error that carries an unread Response", async () => {
      const response = new Response(
         JSON.stringify({ detail: "Host is unavailable" }),
         { status: 503 }
      );
      const error = Object.assign(new Error("host error"), { response });

      await expect(normalizeApiError(error)).resolves.toMatchObject({
         status: 503,
         messages: ["Host is unavailable"]
      });
   });

   it("returns the generic fallback for unknown errors", async () => {
      await expect(normalizeApiError(new Error("boom"))).resolves.toEqual(
         createFallbackApiError()
      );
   });
});
