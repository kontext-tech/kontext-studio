import type { InlineData } from "@kontext-labs/schema";
import { ProvenanceInfo } from "@kontext-labs/ui";
import { Empty, Tabs } from "antd";
import React from "react";
import QueryResultsTable from "./QueryResultsTable";

export interface DataTablePreviewProps {
   data: InlineData;
   compact?: boolean;
}

/**
 * DataTablePreview - Shared component to display a data table from InlineData
 *
 * When the data table carries generation provenance, a Metadata tab is shown
 * alongside the table so users can trace it back to the notebook, query
 * session, or AI chat session that produced it.
 */
const DataTablePreview: React.FC<DataTablePreviewProps> = ({
   data,
   compact = false
}) => {
   const table = data.table;
   const metadata = data.metadata;
   const hasMetadata =
      !!metadata &&
      Object.values(metadata).some(
         (value) => value !== null && value !== undefined && value !== ""
      );

   const tableNode = table ? (
      <QueryResultsTable result={table} compact={compact} />
   ) : (
      <Empty description="No table data available" />
   );

   if (!hasMetadata) {
      return (
         <div
            className="kontext-data-table-preview"
            style={{ padding: compact ? "12px" : "16px", height: "100%" }}
         >
            {tableNode}
         </div>
      );
   }

   return (
      <div
         className="kontext-data-table-preview"
         style={{ padding: compact ? "12px" : "16px", height: "100%" }}
      >
         <Tabs
            defaultActiveKey="data"
            size="small"
            items={[
               {
                  key: "data",
                  label: "Data",
                  children: tableNode
               },
               {
                  key: "metadata",
                  label: "Metadata",
                  children: (
                     <ProvenanceInfo
                        notebookId={metadata?.notebookId}
                        querySessionId={metadata?.querySessionId}
                        chatSessionId={metadata?.chatSessionId}
                        sql={metadata?.sql}
                        createdAt={metadata?.createdAt}
                        rowCount={metadata?.rowCount}
                     />
                  )
               }
            ]}
         />
      </div>
   );
};

export default DataTablePreview;
