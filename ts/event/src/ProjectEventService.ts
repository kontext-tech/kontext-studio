import type { ApiAuthContext, ApiErrorResult } from "@kontext-tech/common";
import { ApiResult, DataApiBaseService } from "@kontext-tech/common";
import type {
   EventType,
   PaginatedListOfEventModel
} from "@kontext-tech/schema";

/**
 * Service for managing project-level events from the Data-AI API.
 *
 * Project events are stored in project-scoped SQLite databases and track
 * data-related operations like resource and catalog-entity changes.
 */
export class ProjectEventService extends DataApiBaseService {
   constructor(
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) {
      super(authContext, errorHandler);
   }

   async getProjectEvents(
      projectId: string,
      pageIndex: number = 1,
      pageSize: number = 20,
      eventTypes?: EventType[],
      daysLimit: number = 30
   ): Promise<ApiResult<PaginatedListOfEventModel>> {
      try {
         const result = await this.request(
            this.apiClient.GET("/event", {
               params: {
                  query: {
                     projectId,
                     pageIndex,
                     pageSize,
                     eventTypes: eventTypes?.join(","),
                     daysLimit
                  }
               }
            })
         );
         return ApiResult.success(result as PaginatedListOfEventModel);
      } catch (error) {
         return ApiResult.failure(await this.handleApiError(error));
      }
   }
}
