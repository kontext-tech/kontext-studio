import type { ApiErrorResult } from "@kontext-tech/common";
import { useEffect } from "react";
import { useCultureStore } from "./cultureStore";

export interface UseSiteCulturesOptions {
   errorHandler?: (error: ApiErrorResult) => Promise<void>;
}

export function useSiteCultures(options: UseSiteCulturesOptions = {}) {
   const { errorHandler } = options;

   const cultures = useCultureStore((state) => state.cultures);
   const isLoading = useCultureStore((state) => state.isLoading);
   const error = useCultureStore((state) => state.error);
   const lastFetched = useCultureStore((state) => state.lastFetched);
   const fetchCultures = useCultureStore((state) => state.fetchCultures);
   const clearError = useCultureStore((state) => state.clearError);

   useEffect(() => {
      if (cultures.length === 0 && !isLoading && !lastFetched) {
         void fetchCultures(errorHandler);
      }
   }, [cultures.length, errorHandler, fetchCultures, isLoading, lastFetched]);

   return {
      cultures,
      loading: isLoading,
      error,
      fetchCultures: () => fetchCultures(errorHandler),
      clearError
   };
}
