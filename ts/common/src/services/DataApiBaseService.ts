import type { ApiAuthContext, ApiErrorResult } from "../types";
import { getDataApiUrl } from "../utils/envUtils";
import { ApiBaseService } from "./ApiBaseService";

/**
 * Base class for services using the Data API.
 * Points the shared openapi-fetch client at the Data API origin.
 */
export abstract class DataApiBaseService extends ApiBaseService {
   /**
    * @param authContext Authentication context
    * @param errorHandler Optional error handler
    */
   constructor(
      authContext: ApiAuthContext,
      errorHandler?: (error: ApiErrorResult) => Promise<void>
   ) {
      super(
         authContext,
         errorHandler,
         // Use the Data API URL
         getDataApiUrl()
      );
   }
}
