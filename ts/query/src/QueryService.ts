import { ApiResult, DataApiBaseService } from "@kontext-tech/common";
import type { QueryExecRequest, QueryResponse } from "@kontext-tech/schema";

/**
 * Service for query operations via the Data API
 * Provides direct access to query execution functionality
 */
export class QueryService extends DataApiBaseService {
   /**
    * Execute a query in the specified session
    * @param request Query execution parameters
    * @returns Promise resolving to query execution response
    */
   async executeQuery(
      request: QueryExecRequest
   ): Promise<ApiResult<QueryResponse>> {
      return this.wrap(async () => {
         const response = await this.request(
            this.apiClient.POST("/query/execute", {
               body: request
            })
         );
         return response as QueryResponse;
      });
   }
}
