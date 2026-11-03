import type { ApiAuthContext, ApiErrorResult } from "@kontext-labs/common";
import { ApiResult, DataApiBaseService } from "@kontext-labs/common";
import type { OkfConcept } from "@kontext-labs/schema";
import type { paths } from "@kontext-labs/schema/api";

/** JSON request body for the OKF upsert endpoint, derived from the spec. */
type UpsertConceptBody =
   paths["/catalog/okf/concepts/{concept_id}"]["put"] extends {
      requestBody: { content: { "application/json": infer Body } };
   }
      ? Body
      : never;

/**
 * Wraps the OKF endpoints behind the `ApiResult` contract used across the app.
 * Covers the full OKF v0.2 curation surface: list/get/search, agent proposals
 * + approval, upsert/delete, and portable bundle export/import.
 */
export class KnowledgeService extends DataApiBaseService {
   constructor(
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) {
      super(authContext, errorHandler);
   }

   async listConcepts(projectId: string): Promise<ApiResult<OkfConcept[]>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/catalog/okf/concepts", {
               params: { query: { projectId } }
            })
         );
         return ApiResult.success(result as OkfConcept[]);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async searchConcepts(
      projectId: string,
      query: string,
      limit = 10
   ): Promise<ApiResult<OkfConcept[]>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/catalog/okf/concepts/search", {
               params: {
                  query: { projectId, query, limit }
               }
            })
         );
         return ApiResult.success(result as OkfConcept[]);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async getConcept(
      projectId: string,
      conceptId: string
   ): Promise<ApiResult<OkfConcept | null>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/catalog/okf/concepts/{concept_id}", {
               params: {
                  path: { concept_id: conceptId },
                  query: { projectId }
               }
            })
         );
         return ApiResult.success(result as OkfConcept);
      } catch (error) {
         if (this.getErrorStatus(error) === 404) {
            return ApiResult.success(null);
         }
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async listProposals(projectId: string): Promise<ApiResult<OkfConcept[]>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/catalog/okf/proposals", {
               params: { query: { projectId } }
            })
         );
         return ApiResult.success(result as OkfConcept[]);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async approveProposal(
      projectId: string,
      conceptId: string
   ): Promise<ApiResult<OkfConcept>> {
      try {
         const result = await this.request(
            this.apiClient.POST("/catalog/okf/proposals/{concept_id}/approve", {
               params: {
                  path: { concept_id: conceptId },
                  query: { projectId }
               }
            })
         );
         return ApiResult.success(result as OkfConcept);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async upsertConcept(
      projectId: string,
      conceptId: string,
      concept: OkfConcept
   ): Promise<ApiResult<OkfConcept>> {
      try {
         const result = await this.request(
            this.apiClient.PUT("/catalog/okf/concepts/{concept_id}", {
               params: {
                  path: { concept_id: conceptId },
                  query: { projectId }
               },
               // The OpenAPI export renders Zod's `.catchall()` as an
               // `additionalProperties` field, so the generated request body
               // does not structurally match the Zod type.
               body: concept as unknown as UpsertConceptBody
            })
         );
         return ApiResult.success(result as OkfConcept);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async deleteConcept(
      projectId: string,
      conceptId: string
   ): Promise<ApiResult<void>> {
      try {
         await this.request(
            this.apiClient.DELETE("/catalog/okf/concepts/{concept_id}", {
               params: {
                  path: { concept_id: conceptId },
                  query: { projectId }
               }
            })
         );
         return ApiResult.success(undefined);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async exportBundle(projectId: string): Promise<ApiResult<void>> {
      try {
         const blob = await this.request(
            this.apiClient.GET("/catalog/okf/export", {
               params: { query: { projectId } },
               parseAs: "blob"
            })
         );
         const url = window.URL.createObjectURL(blob);
         const link = document.createElement("a");
         link.href = url;
         link.download = `okf-bundle-${projectId}.tar.gz`;
         document.body.appendChild(link);
         link.click();
         document.body.removeChild(link);
         window.URL.revokeObjectURL(url);
         return ApiResult.success(undefined);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }

   async importBundle(
      projectId: string,
      file: Blob
   ): Promise<ApiResult<OkfImportResult>> {
      try {
         const formData = new FormData();
         formData.append("file", file);
         const result = await this.request(
            this.apiClient.POST("/catalog/okf/import", {
               params: { query: { projectId } },
               body: formData as unknown as { file: string }
            })
         );
         // Untyped payload from the generated contract; assert to the service contract.
         return ApiResult.success(result as unknown as OkfImportResult);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }
}

export interface OkfImportResult {
   readonly importedConceptCount: number;
   /** OKF §11 conformance problems found in reserved/structural files. */
   readonly conformanceWarnings?: string[];
}
