import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useDataService } from "@kontext-tech/app-runtime/hooks";
import { KnowledgeService, type OkfImportResult } from "@kontext-tech/project";
import type { OkfConcept } from "@kontext-tech/schema";
import {
   useMutation,
   useQuery,
   useQueryClient,
   type UseMutationResult
} from "@tanstack/react-query";
import { useCallback } from "react";

export const knowledgeQueryKeys = {
   all: (projectId: string) => ["knowledge", projectId] as const,
   concepts: (projectId: string) =>
      [...knowledgeQueryKeys.all(projectId), "concepts"] as const,
   concept: (projectId: string, conceptId: string) =>
      [...knowledgeQueryKeys.all(projectId), "concept", conceptId] as const,
   proposals: (projectId: string) =>
      [...knowledgeQueryKeys.all(projectId), "proposals"] as const
};

const unwrap = <T>(
   result: { succeed: boolean; data?: T; error?: { title: string } },
   fallback: string
): T => {
   if (!result.succeed || result.data === undefined) {
      throw new Error(result.error?.title || fallback);
   }
   return result.data;
};

const useKnowledgeService = () => {
   const apiErrorHandler = useApiErrorHandler();
   return useDataService(KnowledgeService, apiErrorHandler);
};

export const useKnowledgeConcepts = (projectId?: string | null) => {
   const service = useKnowledgeService();
   return useQuery({
      queryKey: knowledgeQueryKeys.concepts(projectId ?? ""),
      enabled: Boolean(projectId),
      queryFn: async () => {
         const result = await service.listConcepts(projectId as string);
         return unwrap(result, "Failed to load knowledge concepts");
      }
   });
};

export const useKnowledgeConcept = (
   projectId?: string | null,
   conceptId?: string | null
) => {
   const service = useKnowledgeService();
   return useQuery({
      queryKey: knowledgeQueryKeys.concept(projectId ?? "", conceptId ?? ""),
      enabled: Boolean(projectId && conceptId),
      queryFn: async () => {
         const result = await service.getConcept(
            projectId as string,
            conceptId as string
         );
         if (!result.succeed) {
            throw new Error(
               result.error?.title || "Failed to load knowledge concept"
            );
         }
         return result.data ?? null;
      }
   });
};

export const useKnowledgeProposals = (projectId?: string | null) => {
   const service = useKnowledgeService();
   return useQuery({
      queryKey: knowledgeQueryKeys.proposals(projectId ?? ""),
      enabled: Boolean(projectId),
      queryFn: async () => {
         const result = await service.listProposals(projectId as string);
         return unwrap(result, "Failed to load knowledge proposals");
      }
   });
};

const useInvalidateKnowledge = (projectId?: string | null) => {
   const queryClient = useQueryClient();
   return useCallback(() => {
      void queryClient.invalidateQueries({
         queryKey: knowledgeQueryKeys.all(projectId ?? "")
      });
   }, [projectId, queryClient]);
};

export const useUpsertConcept = (
   projectId?: string | null
): UseMutationResult<
   OkfConcept,
   Error,
   { conceptId: string; concept: OkfConcept }
> => {
   const service = useKnowledgeService();
   const invalidate = useInvalidateKnowledge(projectId);
   return useMutation({
      mutationFn: async ({ conceptId, concept }) => {
         const result = await service.upsertConcept(
            projectId as string,
            conceptId,
            concept
         );
         return unwrap(result, "Failed to save knowledge concept");
      },
      onSuccess: invalidate
   });
};

export const useDeleteConcept = (
   projectId?: string | null
): UseMutationResult<void, Error, string> => {
   const service = useKnowledgeService();
   const invalidate = useInvalidateKnowledge(projectId);
   return useMutation({
      mutationFn: async (conceptId: string) => {
         const result = await service.deleteConcept(
            projectId as string,
            conceptId
         );
         if (!result.succeed) {
            throw new Error(
               result.error?.title || "Failed to delete knowledge concept"
            );
         }
      },
      onSuccess: invalidate
   });
};

export const useApproveProposal = (
   projectId?: string | null
): UseMutationResult<OkfConcept, Error, string> => {
   const service = useKnowledgeService();
   const invalidate = useInvalidateKnowledge(projectId);
   return useMutation({
      mutationFn: async (conceptId: string) => {
         const result = await service.approveProposal(
            projectId as string,
            conceptId
         );
         return unwrap(result, "Failed to approve proposal");
      },
      onSuccess: invalidate
   });
};

export const useExportBundle = (projectId?: string | null) => {
   const service = useKnowledgeService();
   return useMutation({
      mutationFn: async () => {
         const result = await service.exportBundle(projectId as string);
         if (!result.succeed) {
            throw new Error(result.error?.title || "Failed to export bundle");
         }
      }
   });
};

export const useImportBundle = (
   projectId?: string | null
): UseMutationResult<OkfImportResult, Error, Blob> => {
   const service = useKnowledgeService();
   const invalidate = useInvalidateKnowledge(projectId);
   return useMutation({
      mutationFn: async (file: Blob) => {
         const result = await service.importBundle(projectId as string, file);
         return unwrap(result, "Failed to import bundle");
      },
      onSuccess: invalidate
   });
};
