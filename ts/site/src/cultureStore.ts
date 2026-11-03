import type { CultureInfoModel } from "@kontext-labs/schema";
import { create } from "zustand";
import { ServiceContainer } from "@kontext-labs/common";
import type { ApiErrorResult } from "@kontext-labs/common";
import { SiteCultureService } from "./SiteCultureService";

const cultureServiceContainer = new ServiceContainer();

function getSiteCultureService(
   errorHandler?: (error: ApiErrorResult) => Promise<void>
) {
   cultureServiceContainer.setAuthContext({});
   cultureServiceContainer.setErrorHandler(errorHandler);

   return cultureServiceContainer.getOrCreate(
      "culture-service",
      (container: ServiceContainer) => {
         return new SiteCultureService(
            container.createAuthContext(),
            container.getErrorHandler()
         );
      }
   );
}

interface CultureState {
   // State
   cultures: CultureInfoModel[];
   isLoading: boolean;
   error: string | null;
   lastFetched: Date | null;

   // Actions
   fetchCultures: (
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) => Promise<void>;
   clearError: () => void;
}

export const useCultureStore = create<CultureState>((set, get) => ({
   // Initial state
   cultures: [],
   isLoading: false,
   error: null,
   lastFetched: null,

   fetchCultures: async (errorHandler) => {
      const state = get();

      // If we have cultures and fetched them recently, don't fetch again
      if (state.cultures.length > 0 && state.lastFetched) {
         const timeSinceLastFetch = Date.now() - state.lastFetched.getTime();
         const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes
         if (timeSinceLastFetch < CACHE_DURATION) {
            return;
         }
      }

      set({ isLoading: true, error: null });

      try {
         const result = await getSiteCultureService(errorHandler).getCultures();

         if (result.succeed && result.data) {
            set({
               cultures: result.data,
               isLoading: false,
               error: null,
               lastFetched: new Date()
            });
         } else {
            const errorMessage =
               result.error?.messages?.[0] || "Failed to load cultures";
            set({
               isLoading: false,
               error: errorMessage
            });
         }
      } catch (error) {
         const errorMessage =
            error instanceof Error ? error.message : "Failed to load cultures";
         set({
            isLoading: false,
            error: errorMessage
         });
      }
   },

   clearError: () => {
      set({ error: null });
   }
}));
