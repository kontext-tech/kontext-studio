import type { ApiErrorResult } from "@kontext-labs/common";
import { useService } from "@kontext-labs/app-runtime/hooks";
import type { ProjectModel } from "@kontext-labs/schema";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ProjectService } from "./ProjectService";
import { projectQueryKeys } from "./projectQueryKeys";

export interface ProjectListingOptions {
   initialPageSize?: number;
   initialIncludePublic?: boolean;
   initialSearchText?: string;
   initialRoleFilters?: string[];
   includePrivate?: boolean;
   includeDeleted?: boolean;
   lazy?: boolean;
}

export interface ProjectListingState {
   projects: ProjectModel[];
   isLoading: boolean;
   error: string | null;
   pageIndex: number;
   pageSize: number;
   totalCount: number;
   totalPages: number;
   searchText: string;
   roleFilters: string[] | undefined;
   includePublic: boolean;
   setPageIndex: (page: number) => void;
   setPageSize: (size: number) => void;
   setSearchText: (text: string) => void;
   setRoleFilters: (filters: string[] | undefined) => void;
   setIncludePublic: (include: boolean) => void;
   resetFilters: () => void;
   loadProjects: () => void;
}

export function useProjectListing(
   options: ProjectListingOptions = {},
   errorHandler?: (error: ApiErrorResult) => Promise<void>
): ProjectListingState {
   const {
      initialPageSize = 10,
      initialIncludePublic = false,
      initialSearchText = "",
      initialRoleFilters = undefined,
      includePrivate = true,
      includeDeleted = false,
      lazy = false
   } = options;

   const [pageIndex, setPageIndex] = useState<number>(1);
   const [pageSize, setPageSize] = useState<number>(initialPageSize);
   const [searchText, setSearchText] = useState<string>(initialSearchText);
   const [roleFilters, setRoleFilters] = useState<string[] | undefined>(
      initialRoleFilters
   );
   const [includePublic, setIncludePublic] =
      useState<boolean>(initialIncludePublic);
   const [hasRequestedLoad, setHasRequestedLoad] = useState(!lazy);
   const hasRequestedLoadRef = useRef(hasRequestedLoad);

   const projectService = useService(ProjectService, errorHandler);

   const listingQueryKey = useMemo(
      () =>
         projectQueryKeys.listing({
            searchText,
            pageIndex,
            pageSize,
            roleFilters,
            includePublic,
            includePrivate,
            includeDeleted
         }),
      [
         includeDeleted,
         includePrivate,
         includePublic,
         pageIndex,
         pageSize,
         roleFilters,
         searchText
      ]
   );

   const projectListingQuery = useQuery({
      queryKey: listingQueryKey,
      enabled: hasRequestedLoad,
      placeholderData: keepPreviousData,
      queryFn: async () => {
         const response = await projectService.getFilteredProjects(
            searchText || undefined,
            pageIndex,
            pageSize,
            roleFilters,
            includePublic,
            includePrivate,
            includeDeleted
         );

         if (!response.succeed || !response.data) {
            throw new Error(response.error?.title || "Failed to load projects");
         }

         return response.data;
      }
   });
   const refetchProjects = projectListingQuery.refetch;

   useEffect(() => {
      hasRequestedLoadRef.current = hasRequestedLoad;
   }, [hasRequestedLoad]);

   const resetFilters = useCallback(() => {
      setSearchText(initialSearchText);
      setRoleFilters(initialRoleFilters);
      setIncludePublic(initialIncludePublic);
      setPageIndex(1);
   }, [initialSearchText, initialRoleFilters, initialIncludePublic]);

   const loadProjects = useCallback(() => {
      if (!hasRequestedLoadRef.current) {
         setHasRequestedLoad(true);
         return;
      }

      void refetchProjects();
   }, [refetchProjects]);

   const projects = projectListingQuery.data?.items || [];
   const totalCount = projectListingQuery.data?.totalCount || 0;
   const totalPages = projectListingQuery.data?.totalPages || 1;
   const isLoading =
      projectListingQuery.isLoading || projectListingQuery.isFetching;
   const error =
      projectListingQuery.error instanceof Error
         ? projectListingQuery.error.message
         : null;

   return {
      projects,
      isLoading,
      error,
      pageIndex,
      pageSize,
      totalCount,
      totalPages,
      searchText,
      roleFilters,
      includePublic,
      setPageIndex,
      setPageSize,
      setSearchText,
      setRoleFilters,
      setIncludePublic,
      resetFilters,
      loadProjects
   };
}
