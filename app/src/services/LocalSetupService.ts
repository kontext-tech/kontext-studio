import { API_BASE_PATH } from "@kontext-labs/common";
import type {
   AccessTokenResponse,
   SetupRequest,
   SetupStatusResponse
} from "@kontext-labs/schema";

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
      const response = await fetch(`${API_BASE_PATH}${path}`, init);

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
