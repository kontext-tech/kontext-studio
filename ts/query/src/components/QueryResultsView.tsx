import type { QueryResponse } from "@kontext-tech/schema";
import { Alert } from "antd";
import React from "react";
import QueryResultsTable from "./QueryResultsTable";

interface QueryResultsViewProps {
   response: QueryResponse;
   loading?: boolean;
   compact?: boolean;
}

/**
 * QueryResultsView - Displays results from SQL statement execution
 * Simplified logic: Show error if failed, otherwise show results
 */
const QueryResultsView: React.FC<QueryResultsViewProps> = ({
   response,
   loading = false,
   compact = false
}) => {
   const result = response.result;
   const hasError = response.success === false;
   const errorMessage = response.errorMessage;

   // If there's an error, show it prominently
   if (hasError && errorMessage) {
      return (
         <Alert
            type="error"
            title="Query Execution Failed"
            description={errorMessage}
            showIcon
         />
      );
   }

   // If no result, show info message
   if (!result) {
      return (
         <Alert
            type="info"
            title="No results"
            description="Query executed successfully but returned no data."
         />
      );
   }

   const hasData = (result.rows?.length || 0) > 0 || (result.rowCount || 0) > 0;

   if (hasData) {
      return (
         <QueryResultsTable
            result={result}
            loading={loading}
            compact={compact}
         />
      );
   }

   // Statement with no data (DDL/DML)
   return (
      <Alert
         type="info"
         title="Statement executed successfully"
         description="No data returned. This is typical for CREATE, INSERT, UPDATE, DELETE statements."
      />
   );
};

export default QueryResultsView;
