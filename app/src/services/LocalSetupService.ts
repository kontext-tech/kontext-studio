import {
   API_BASE_PATH,
   LAUNCH_TOKEN_HEADER,
   getLaunchToken
} from "@kontext-tech/common";
import type {
   AccessTokenResponse,
   SetupRequest,
   SetupStatusResponse
} from "@kontext-tech/schema";

export class LocalSetupService {
   async getStatus(): Promise<SetupStatusResponse> {
      return this.request<SetupStatusResponse>("/setup/status");
   }

   async completeSetup(request: SetupRequest): Promise<AccessTokenResponse> {
      return this.request<AccessTokenResponse>("/setup", {
         method: "POST",
         headers: {
            "Content-Type": "application/json"
         },
         body: JSON.stringify(request)
      });
   }

   private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
      const headers = new Headers(init.headers);
      const launchToken = getLaunchToken();
      if (launchToken) {
         headers.set(LAUNCH_TOKEN_HEADER, launchToken);
      }

      const response = await fetch(`${API_BASE_PATH}${path}`, {
         ...init,
         // Send and accept cookies so the session survives browser-native
         // requests and cross-origin dev setups.
         credentials: init.credentials ?? "include",
         headers
      });

      if (!response.ok) {
         let message = "Request failed.";
         try {
            const errorPayload = (await response.json()) as {
               detail?: string;
               title?: string;
            };
            message = errorPayload.detail || errorPayload.title || message;
         } catch {
            // Keep the default message when the error body is empty or invalid.
         }
         throw new Error(message);
      }

      return (await response.json()) as T;
   }
}
