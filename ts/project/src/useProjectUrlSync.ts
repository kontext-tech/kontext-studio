import type { ApiErrorResult } from "@kontext-labs/common";
import { useEffect } from "react";
import { useProjectStore } from "./projectStore";

export interface UseProjectUrlSyncOptions {
   accessToken?: string;
   errorHandler?: (error: ApiErrorResult) => Promise<void>;
}

export const useProjectUrlSync = (
   projectCode?: string,
   options: UseProjectUrlSyncOptions = {}
) => {
   const { accessToken, errorHandler } = options;

   useEffect(() => {
      void useProjectStore
         .getState()
         .syncWithUrl(projectCode, accessToken, errorHandler);
   }, [accessToken, errorHandler, projectCode]);
};
