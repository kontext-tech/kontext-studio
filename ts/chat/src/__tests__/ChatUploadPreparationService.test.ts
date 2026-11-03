/** @jest-environment node */
/// <reference types="jest" />

import { ProblemTypes } from "@kontext-labs/schema";
import { ChatUploadPreparationService } from "../ChatUploadPreparationService";

const jsonResponse = (body: unknown, status: number): Response =>
   new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" }
   });

describe("ChatUploadPreparationService", () => {
   const runId = "11111111-1111-1111-1111-111111111111";
   const connectionId = "22222222-2222-2222-2222-222222222222";

   beforeEach(() => {
      global.fetch = jest.fn() as unknown as typeof fetch;
   });

   afterEach(() => {
      jest.resetAllMocks();
   });

   it("starts a chat upload preparation with multipart form data", async () => {
      (global.fetch as jest.Mock).mockResolvedValue(
         jsonResponse(
            {
               runId,
               internalCatalogConnectionId: connectionId,
               acceptedFiles: [
                  {
                     fileId: "33333333-3333-3333-3333-333333333333",
                     filename: "orders.csv",
                     fileType: "CSV",
                     size: 14
                  }
               ],
               uploadErrors: [],
               successCount: 1,
               failureCount: 0
            },
            201
         )
      );

      const service = new ChatUploadPreparationService({
         accessToken: "token-123"
      });
      const file = new File(["id,total\n1,10\n"], "orders.csv", {
         type: "text/csv"
      });

      const result = await service.startUploadPreparation(
         "project-1",
         [file],
         true
      );

      expect(result.succeed).toBe(true);
      expect(result.data?.runId).toBe(runId);

      const request = (global.fetch as jest.Mock).mock.calls[0][0] as Request;
      expect(request.url).toContain(
         "/ai/chat/upload-preparations?projectId=project-1&allowOverwrite=true"
      );
      expect(request.method).toBe("POST");
      expect(request.headers.get("Authorization")).toBe("Bearer token-123");
      const body = await request.clone().formData();
      expect(body.getAll("files")).toHaveLength(1);
   });

   it("loads normalized upload preparation status", async () => {
      (global.fetch as jest.Mock).mockResolvedValue(
         jsonResponse(
            {
               runId,
               status: "failed",
               progress: 100,
               internalCatalogConnectionId: connectionId,
               readyFileIds: ["33333333-3333-3333-3333-333333333333"],
               failedFiles: [
                  {
                     filename: "customers.csv",
                     error: "Profiling returned no schema"
                  }
               ],
               steps: [
                  {
                     key: "lakehouse-ingest",
                     name: "Lakehouse ingest",
                     status: "failed",
                     runId: "44444444-4444-4444-4444-444444444444",
                     progress: 100,
                     errorMessage:
                        "Lakehouse ingest completed with 1 failure(s)"
                  }
               ]
            },
            200
         )
      );

      const service = new ChatUploadPreparationService({});
      const result = await service.getUploadPreparationStatus(
         "project-1",
         runId
      );

      expect(result.succeed).toBe(true);
      expect(result.data?.readyFileIds).toEqual([
         "33333333-3333-3333-3333-333333333333"
      ]);
      expect(result.data?.failedFiles[0]?.filename).toBe("customers.csv");

      const request = (global.fetch as jest.Mock).mock.calls[0][0] as Request;
      expect(request.url).toContain(
         `/ai/chat/upload-preparations/${runId}?projectId=project-1`
      );
      expect(request.method).toBe("GET");
   });

   it("preserves structured error bodies after openapi-fetch consumes them", async () => {
      (global.fetch as jest.Mock).mockResolvedValue(
         jsonResponse(
            {
               type: ProblemTypes.UnsupportedTokenVersion,
               title: "Re-authentication required",
               status: 401,
               detail: "Your session is no longer valid."
            },
            401
         )
      );

      const service = new ChatUploadPreparationService({});
      const result = await service.getUploadPreparationStatus(
         "project-1",
         runId
      );

      expect(result.succeed).toBe(false);
      expect(result.error?.status).toBe(401);
      expect(result.error?.isReauthRequired).toBe(true);
      expect(result.error?.messages[0]).toBe(
         "Your session is no longer valid."
      );
   });

   it("seeds chat attachment context before the first message", async () => {
      (global.fetch as jest.Mock).mockResolvedValue(
         new Response(null, { status: 204 })
      );

      const service = new ChatUploadPreparationService({
         accessToken: "token-123"
      });
      const result = await service.seedChatAttachmentContext(
         "project-1",
         "55555555-5555-5555-5555-555555555555",
         runId
      );

      expect(result.succeed).toBe(true);

      const request = (global.fetch as jest.Mock).mock.calls[0][0] as Request;
      expect(request.url).toContain(
         "/ai/chat/session/55555555-5555-5555-5555-555555555555/attachment-context?projectId=project-1"
      );
      expect(request.method).toBe("POST");
      expect(request.headers.get("Authorization")).toBe("Bearer token-123");
      expect(request.headers.get("Content-Type")).toBe("application/json");
      expect(await request.clone().json()).toEqual({
         uploadPreparationRunId: runId
      });
   });
});
