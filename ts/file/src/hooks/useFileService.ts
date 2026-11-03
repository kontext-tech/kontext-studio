import type { ApiErrorResult } from "@kontext-tech/common/types";
import { useDataService } from "@kontext-tech/app-runtime/hooks";
import { FileService } from "../services";

export function useFileService(
   errorHandler?: (errorResult: ApiErrorResult) => Promise<void>
) {
   return useDataService(FileService, errorHandler);
}
