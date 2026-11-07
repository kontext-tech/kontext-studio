import { SiteFeature, type SiteConfigResponse } from "@kontext-tech/schema";
import { create } from "zustand";
import { API_BASE_PATH } from "@kontext-tech/common";

export interface SiteConfigState {
   siteConfig: SiteConfigResponse | null;
   setSiteConfig: (config: SiteConfigResponse | null) => void;
   /** Fetch GET /config/site, cache as siteConfig, return the result. */
   fetchSiteConfig: () => Promise<SiteConfigResponse | null>;
}

export const useSiteConfigStore = create<SiteConfigState>()((set) => ({
   siteConfig: null,

   setSiteConfig: (config) => {
      set({ siteConfig: config });
   },

   fetchSiteConfig: async () => {
      try {
         const res = await fetch(`${API_BASE_PATH}/config/site`);
         if (!res.ok) return null;
         const config = (await res.json()) as SiteConfigResponse;
         set({ siteConfig: config });
         return config;
      } catch {
         return null;
      }
   }
}));

export function useIsLocalMode(): boolean {
   return useSiteConfigStore(
      (state) =>
         state.siteConfig?.features?.includes(SiteFeature.LOCAL_MODE) ?? false
   );
}
