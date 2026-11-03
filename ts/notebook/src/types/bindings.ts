import type {
   CodeExecutionOutput,
   DataRef,
   DataTable,
   DataTableSummary
} from "@kontext-labs/schema";

interface BindingError {
   messages: string[];
}

interface BindingResult<T> {
   succeed: boolean;
   data?: T;
   error?: BindingError;
}

export interface CodeExecutionResult {
   status: "success" | "error";
   outputs: CodeExecutionOutput[];
   error?: string;
   executionRunId?: string;
   executionMode?: "draft" | "persisted";
   executionTimeMs?: number;
}

export interface CellExecutionContext {
   notebookId?: string;
   blockId?: string;
}

export interface CellExecutionResult {
   status: "success" | "error";
   output?: unknown;
   error?: string;
   executionRunId?: string;
   executionMode?: "draft" | "persisted";
   executionTimeMs?: number;
}

export interface CodeExecutionEngine {
   execute(
      code: string,
      context?: CellExecutionContext,
      language?: string
   ): Promise<CodeExecutionResult>;
   executeCell?(
      language: string,
      code: string,
      context?: CellExecutionContext
   ): Promise<CellExecutionResult>;
   /**
    * Request cancellation of the run currently executing for this cell.
    * Returns true when a matching in-flight run was found and cancelled.
    */
   cancelExecution?(context?: CellExecutionContext): Promise<boolean>;
}

export interface FileSystemBinding {
   uploadImage(
      fileOrProjectId: File | Blob | string,
      file?: File | Blob
   ): Promise<BindingResult<{ url: string }> | string>;
   getFileUrl(fileId: string): string | Promise<string>;
   getInlineData?(
      fileId: string,
      projectId?: string
   ): Promise<BindingResult<DataTable>>;
   downloadFile?(
      fileId: string,
      projectId?: string,
      onProgress?: (progress: number) => void
   ): Promise<BindingResult<{ blob: Blob; filename?: string }>>;
   getPaginatedImageFiles?(
      projectId?: string,
      pageIndex?: number,
      pageSize?: number,
      search?: string
   ): Promise<BindingResult<{ items: unknown[]; totalCount: number }>>;
}

export interface DataCatalogBinding {
   getSchemas(): Promise<unknown[]>;
   getEnvironments?(): Promise<unknown[]>;
}

export interface DataResolverBinding {
   listDataRefs?(
      projectId?: string,
      search?: string
   ): Promise<
      BindingResult<
         Array<{
            ref: DataRef;
            title: string;
            description?: string;
            summary?: DataTableSummary;
         }>
      >
   >;
   resolveData(
      ref: DataRef,
      projectId?: string
   ): Promise<BindingResult<DataTable>>;
   getDataSummary?(
      ref: DataRef,
      projectId?: string
   ): Promise<BindingResult<DataTableSummary>>;
}
