import type { ApiErrorResult } from "@kontext-labs/common/types";
import { useDataService } from "@kontext-labs/app-runtime/hooks";
import { FileService } from "../services";

export function useFileService(
   errorHandler?: (errorResult: ApiErrorResult) => Promise<void>
) {
   return useDataService(FileService, errorHandler);
}
