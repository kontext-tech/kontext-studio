import { ApiResult, type PaginatedResult } from "@kontext-labs/common";
import type { FileServiceContract } from "@kontext-labs/file";
import type {
   FileFormatType,
   FileModel,
   InlineData,
   PythonExecutionResult
} from "@kontext-labs/schema";

interface MockResource {
   id: string;
   name: string;
   contentType: string;
   fileType: FileFormatType;
   blob?: Blob;
   inlineData?: InlineData;
   projectId: string;
   ownerId: string;
   size: number;
   dateCreated: string;
   dateModified: string;
}

/**
 * Mock implementation of resource service methods for testing and demos
 * This provides a simple in-memory store for both data tables and file resources
 * (images, documents, etc.) created during notebook operations
 */
export class MockResourceService implements FileServiceContract {
   private resources: Map<string, MockResource> = new Map();

   /**
    * Store a data table in the mock resource store
    * This simulates what happens when the backend stores query results as a .dt resource file
    */
   storeInlineData(resourceId: string, inlineData: InlineData): void {
      const existing = this.resources.get(resourceId);
      if (existing) {
         existing.inlineData = inlineData;
      } else {
         this.resources.set(resourceId, {
            id: resourceId,
            name: `${inlineData.title}.dt`,
            contentType: "application/json",
            fileType: "DataTable",
            inlineData: inlineData,
            projectId: "550e8400-e29b-41d4-a716-446655440000",
            ownerId: "demo-user",
            size: JSON.stringify(inlineData).length,
            dateCreated: new Date().toISOString(),
            dateModified: new Date().toISOString()
         });
      }
      console.log(
         "🎯 MockResourceService: Stored data table with resourceId:",
         resourceId,
         "Table present:",
         !!inlineData.table
      );
   }

   /**
    * Retrieve a page of rows from a stored data table.
    * Mirrors the backend rows endpoint so preview-only data tables can be
    * expanded to their full row set in the standalone demo.
    */
   async getDataTableRows(
      fileId: string,
      _projectId: string,
      offset: number,
      limit: number
   ): Promise<ApiResult<InlineData>> {
      const resource = this.resources.get(fileId);
      if (!resource?.inlineData) {
         return {
            succeed: false,
            error: {
               title: "Resource Not Found",
               status: 404,
               messages: [
                  `Data table with resource ID ${fileId} not found in mock store`
               ]
            }
         };
      }

      const rows = resource.inlineData.table?.rows ?? [];
      return {
         succeed: true,
         data: {
            ...resource.inlineData,
            table: {
               ...resource.inlineData.table,
               rows: rows.slice(offset, offset + limit)
            }
         }
      };
   }

   /**
    * Retrieve a data table from the mock resource store
    * This simulates the ResourceService.getDataTableFile method
    */
   async getDataTableFile(
      fileId: string,
      _projectId: string
   ): Promise<ApiResult<InlineData>> {
      console.log(
         "🎯 MockResourceService: Fetching data table with resourceId:",
         fileId
      );

      const resource = this.resources.get(fileId);
      if (!resource?.inlineData) {
         console.warn(
            "🎯 MockResourceService: Data table not found for resourceId:",
            fileId
         );
         return {
            succeed: false,
            error: {
               title: "Resource Not Found",
               status: 404,
               messages: [
                  `Data table with resource ID ${fileId} not found in mock store`
               ]
            }
         };
      }

      console.log(
         "🎯 MockResourceService: Found data table with",
         resource.inlineData.table ? 1 : 0,
         "tables"
      );
      return { succeed: true, data: resource.inlineData };
   }

   /**
    * Upload an image and return file metadata
    */
   async uploadImage(
      projectId: string,
      file: File | Blob
   ): Promise<ApiResult<{ file: FileModel; url: string }>> {
      const fileId = crypto.randomUUID();
      const name = file instanceof File ? file.name : `image-${Date.now()}.png`;

      const resource: MockResource = {
         id: fileId,
         name: name,
         contentType: file.type || "image/png",
         fileType: "Image",
         blob: file,
         projectId: projectId,
         ownerId: "demo-user",
         size: file.size,
         dateCreated: new Date().toISOString(),
         dateModified: new Date().toISOString()
      };

      this.resources.set(fileId, resource);

      console.log("🎯 MockResourceService: Uploaded image:", fileId, name);

      const fileModel: FileModel = {
         id: resource.id,
         name: resource.name,
         contentType: resource.contentType,
         path: resource.name,
         fileType: "Image",
         size: resource.size,
         projectId: resource.projectId,
         ownerId: resource.ownerId,
         dateCreated: resource.dateCreated,
         dateModified: resource.dateModified,
         isDeleted: false
      };

      return {
         succeed: true,
         data: {
            file: fileModel,
            url: this.getFileUrl(fileId)
         }
      };
   }

   /**
    * Get paginated list of image resources
    */
   async getPaginatedImageFiles(
      projectId: string,
      pageIndex: number,
      pageSize: number,
      search: string
   ): Promise<ApiResult<PaginatedResult<FileModel>>> {
      console.log(
         "🎯 MockResourceService: Fetching images - page:",
         pageIndex,
         "size:",
         pageSize,
         "search:",
         search
      );

      // Filter image resources for this project
      const imageResources = Array.from(this.resources.values()).filter(
         (r) =>
            r.projectId === projectId &&
            r.contentType.startsWith("image/") &&
            (!search || r.name.toLowerCase().includes(search.toLowerCase()))
      );

      // Generate additional mock resources if needed (for demo purposes)
      const totalMockCount = Math.max(11, imageResources.length);
      const mockResources: FileModel[] = [];

      for (let i = 0; i < pageSize; i++) {
         const index = pageIndex * pageSize + i;
         if (index >= totalMockCount) break;

         // Use real resource if available, otherwise generate mock
         const realResource = imageResources[i];
         if (realResource) {
            mockResources.push({
               id: realResource.id,
               name: realResource.name,
               contentType: realResource.contentType,
               path: realResource.name,
               fileType: realResource.fileType || "Image",
               size: realResource.size,
               projectId: realResource.projectId,
               ownerId: realResource.ownerId,
               dateCreated: realResource.dateCreated,
               dateModified: realResource.dateModified,
               isDeleted: false
            });
         } else {
            const id = `mock-img-${index}`;
            mockResources.push({
               id,
               name: `Mock Image ${index + 1}.jpg`,
               contentType: "image/jpeg",
               path: `Mock Image ${index + 1}.jpg`,
               fileType: "Image",
               size: Math.floor(Math.random() * 1024 * 1024),
               projectId: projectId,
               ownerId: "demo-user",
               dateCreated: new Date(
                  Date.now() - Math.random() * 30 * 24 * 60 * 60 * 1000
               ).toISOString(),
               dateModified: new Date().toISOString(),
               isDeleted: false
            });
         }
      }

      return {
         succeed: true,
         data: {
            items: mockResources,
            totalCount: totalMockCount
         }
      };
   }

   /**
    * Download a resource (image or data table) with progress tracking
    */
   async downloadFile(
      resourceId: string,
      _projectId: string,
      onProgress?: (progress: number) => void
   ): Promise<ApiResult<{ blob: Blob; filename: string }>> {
      console.log("🎯 MockResourceService: Downloading resource:", resourceId);

      // Simulate download progress
      if (onProgress) {
         for (let p = 0; p <= 100; p += 10) {
            await new Promise((resolve) => setTimeout(resolve, 50));
            onProgress(p);
         }
      }

      const resource = this.resources.get(resourceId);

      // If we have a real blob, return it
      if (resource?.blob) {
         return {
            succeed: true,
            data: {
               blob: resource.blob,
               filename: resource.name
            }
         };
      }

      // Generate a mock image for mock resources
      const canvas = document.createElement("canvas");
      canvas.width = 200;
      canvas.height = 150;
      const ctx = canvas.getContext("2d");
      if (ctx) {
         ctx.fillStyle = "#f0f0f0";
         ctx.fillRect(0, 0, 200, 150);
         ctx.fillStyle = "#333333";
         ctx.font = "14px Arial";
         ctx.textAlign = "center";
         ctx.fillText(`Mock Image`, 100, 70);
         ctx.fillText(resourceId.substring(0, 8), 100, 90);
      }

      return new Promise((resolve) => {
         canvas.toBlob((blob: Blob | null) => {
            if (blob) {
               resolve({
                  succeed: true,
                  data: {
                     blob,
                     filename: resource?.name || `${resourceId}.png`
                  }
               });
            } else {
               resolve({
                  succeed: false,
                  error: {
                     title: "Failed to generate image",
                     status: 500,
                     messages: ["Could not create mock image blob"]
                  }
               });
            }
         }, "image/png");
      });
   }

   /**
    * Execute a Python notebook block.
    * The standalone notebook demo does not persist server-backed notebooks,
    * so this mock returns a clear non-success result instead of attempting
    * to emulate the backend execution pipeline.
    */
   async executeNotebookPythonBlock(
      fileId: string,
      blockId: string,
      _projectId: string
   ): Promise<ApiResult<PythonExecutionResult>> {
      const errorMessage =
         "Python notebook execution is not available in the standalone demo.";

      console.log(
         "🎯 MockResourceService: Python execution requested for notebook block:",
         fileId,
         blockId
      );

      return {
         succeed: true,
         data: {
            type: "python_execution",
            success: false,
            message: errorMessage,
            error: errorMessage,
            outputs: [
               {
                  type: "text",
                  mimeType: "text/plain",
                  content: errorMessage
               }
            ]
         }
      };
   }

   /**
    * Get a direct URL to the resource
    */
   getFileUrl(resourceId: string): string {
      // In demo mode, use a blob URL if available
      const resource = this.resources.get(resourceId);
      if (resource?.blob) {
         return URL.createObjectURL(resource.blob);
      }
      // Fallback to a mock URL
      return `/api/resources/${resourceId}`;
   }

   /**
    * Clear all stored resources (useful for testing)
    */
   clearAll(): void {
      // Revoke blob URLs before clearing
      this.resources.forEach((resource) => {
         if (resource.blob) {
            const url = this.getFileUrl(resource.id);
            if (url.startsWith("blob:")) {
               URL.revokeObjectURL(url);
            }
         }
      });
      this.resources.clear();
      console.log("🎯 MockResourceService: Cleared all resources");
   }

   /**
    * Get the number of stored resources
    */
   getStoredCount(): number {
      return this.resources.size;
   }
}
