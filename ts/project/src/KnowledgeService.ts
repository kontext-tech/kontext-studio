import type { ApiAuthContext, ApiErrorResult } from "@kontext-tech/common";
import {
   ApiResult,
   DataApiBaseService,
   downloadBlob
} from "@kontext-tech/common";
import type { OkfConcept } from "@kontext-tech/schema";
import type { paths } from "@kontext-tech/schema/api";

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
      return this.wrap(async () => {
         const result = await this.request(
            this.apiClient.GET("/catalog/okf/concepts", {
               params: { query: { projectId } }
            })
         );
         return result as OkfConcept[];
      });
   }

   async searchConcepts(
      projectId: string,
      query: string,
      limit = 10
   ): Promise<ApiResult<OkfConcept[]>> {
      return this.wrap(async () => {
         const result = await this.request(
            this.apiClient.GET("/catalog/okf/concepts/search", {
               params: {
                  query: { projectId, query, limit }
               }
            })
         );
         return result as OkfConcept[];
      });
   }

   async getConcept(
      projectId: string,
      conceptId: string
   ): Promise<ApiResult<OkfConcept | null>> {
      return this.wrapOptional(async () => {
         const result = await this.request(
            this.apiClient.GET("/catalog/okf/concepts/{concept_id}", {
               params: {
                  path: { concept_id: conceptId },
                  query: { projectId }
               }
            })
         );
         return result as OkfConcept;
      });
   }

   async listProposals(projectId: string): Promise<ApiResult<OkfConcept[]>> {
      return this.wrap(async () => {
         const result = await this.request(
            this.apiClient.GET("/catalog/okf/proposals", {
               params: { query: { projectId } }
            })
         );
         return result as OkfConcept[];
      });
   }

   async approveProposal(
      projectId: string,
      conceptId: string
   ): Promise<ApiResult<OkfConcept>> {
      return this.wrap(async () => {
         const result = await this.request(
            this.apiClient.POST("/catalog/okf/proposals/{concept_id}/approve", {
               params: {
                  path: { concept_id: conceptId },
                  query: { projectId }
               }
            })
         );
         return result as OkfConcept;
      });
   }

   async upsertConcept(
      projectId: string,
      conceptId: string,
      concept: OkfConcept
   ): Promise<ApiResult<OkfConcept>> {
      return this.wrap(async () => {
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
         return result as OkfConcept;
      });
   }

   async deleteConcept(
      projectId: string,
      conceptId: string
   ): Promise<ApiResult<void>> {
      return this.wrap(async () => {
         await this.request(
            this.apiClient.DELETE("/catalog/okf/concepts/{concept_id}", {
               params: {
                  path: { concept_id: conceptId },
                  query: { projectId }
               }
            })
         );
         return undefined;
      });
   }

   async exportBundle(projectId: string): Promise<ApiResult<void>> {
      return this.wrap(async () => {
         const blob = await this.request(
            this.apiClient.GET("/catalog/okf/export", {
               params: { query: { projectId } },
               parseAs: "blob"
            })
         );
         downloadBlob(blob, `okf-bundle-${projectId}.tar.gz`);
         return undefined;
      });
   }

   async importBundle(
      projectId: string,
      file: Blob
   ): Promise<ApiResult<OkfImportResult>> {
      return this.wrap(async () => {
         const formData = new FormData();
         formData.append("file", file);
         const result = await this.request(
            this.apiClient.POST("/catalog/okf/import", {
               params: { query: { projectId } },
               body: formData as unknown as { file: string }
            })
         );
         // Untyped payload from the generated contract; assert to the service contract.
         return result as unknown as OkfImportResult;
      });
   }
}

export interface OkfImportResult {
   readonly importedConceptCount: number;
   /** OKF §11 conformance problems found in reserved/structural files. */
   readonly conformanceWarnings?: string[];
}
