import { useNotebookStore } from "@notebook/stores/notebookStore";
import { Alert, Select, Space, Typography } from "antd";
import React, { useMemo } from "react";

const { Text } = Typography;

interface InlineDataSelectorProps {
   /** Currently selected data ID (resource ID) */
   selectedInlineDataId?: string;
   /** Callback when data selection changes */
   onInlineDataChange: (dataId: string | undefined) => void;
   /** Whether the selector is readonly */
   readonly?: boolean;
   /** Optional notebook instanceId for multi-instance support */
   instanceId?: string;
}

interface InlineDataOption {
   id: string;
   title: string;
}

/**
 * Inline Data Selector Component
 * Allows users to select from available SQL query results (stored as resources)
 */
export const InlineDataSelector: React.FC<InlineDataSelectorProps> = ({
   selectedInlineDataId,
   onInlineDataChange,
   readonly = false,
   instanceId
}) => {
   // Get all SQL blocks that have results (resource IDs)
   const document = useNotebookStore(
      (state) => state.instances[instanceId || "default"]?.document
   );

   // Build list of available data tables from SQL blocks with results
   const dataTables = useMemo((): InlineDataOption[] => {
      if (!document) return [];

      return document.blocks
         .filter(
            (
               block
            ): block is NonNullable<typeof block> & {
               type: "sql";
               data: { dataId: string; title?: string };
            } =>
               block.type === "sql" &&
               !!(block.data as Record<string, unknown> | undefined)?.dataId
         )
         .map((block) => ({
            id: block.data.dataId,
            title: block.data.title || "SQL Query Result"
         }));
   }, [document]);

   return (
      <Space orientation="vertical" style={{ width: "100%" }} size="large">
         <div>
            <Text strong>Select Data Table</Text>
            <br />
            <Text type="secondary">
               Choose a data table from your notebook to create charts with.
            </Text>
         </div>

         {dataTables.length > 0 ? (
            <Select
               value={selectedInlineDataId}
               onChange={onInlineDataChange}
               style={{ width: "100%" }}
               placeholder="Select a data table"
               disabled={readonly}
            >
               {dataTables.map((ds) => (
                  <Select.Option key={ds.id} value={ds.id}>
                     {ds.title}
                  </Select.Option>
               ))}
            </Select>
         ) : (
            <Alert
               type="warning"
               title="No Data Tables Available"
               description="Run SQL queries in your notebook first to create data tables for charts."
            />
         )}
      </Space>
   );
};
