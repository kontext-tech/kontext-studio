import type { PaginatedResult } from "@kontext-tech/common";
import type { FileModel } from "@kontext-tech/schema";

export interface ImagePickerData {
   resourceId: string;
   caption?: string;
}

export interface ImagePickerConfig {
   onFetchImageResources?: (
      pageIndex: number,
      pageSize: number,
      search: string
   ) => Promise<PaginatedResult<FileModel>>;
   onDownloadImageResource?: (
      resourceId: string,
      onProgress?: (progress: number) => void
   ) => Promise<Blob | null>;
   onGetFileUrl?: (resourceId: string) => Promise<string>;
   readonly?: boolean;
}
