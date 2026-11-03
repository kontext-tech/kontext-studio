import { convertDataTableToRows } from "@kontext-labs/common";
import { PAGE_SIZE_OPTIONS } from "@kontext-labs/common";
import type { DataColumn, DataTable } from "@kontext-labs/schema";
import { Empty, Space, Table, Tooltip, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import React, { useMemo } from "react";

const { Text } = Typography;

export interface QueryResultsTableProps {
   result: DataTable;
   loading?: boolean;
   compact?: boolean;
}

/**
 * QueryResultsTable - Displays SQL query results in a table format
 * Shared component that can be used in both app and notebook projects
 */
const QueryResultsTable: React.FC<QueryResultsTableProps> = ({
   result,
   loading = false,
   compact = false
}) => {
   const { columns } = result;

   // Convert the rows array to objects with column names as keys
   const tableData = useMemo(() => {
      // Use the shared utility for consistent transformation
      const transformResult = convertDataTableToRows(result, {
         addRowIndex: true // Add row index for table keys
      });

      if (!transformResult.success) {
         console.error(
            "Error processing query result rows:",
            transformResult.errorMessage
         );
         return [];
      }

      return transformResult.data;
   }, [result]);

   // Create table columns from query result columns
   const tableColumns: ColumnsType<Record<string, unknown>> = useMemo(() => {
      if (!columns) {
         return [];
      }

      return columns.map((col: DataColumn) => ({
         title: compact ? (
            <Tooltip title={`${col.name} (${col.type})`}>
               <Text strong style={{ fontSize: "12px" }}>
                  {col.name}
               </Text>
            </Tooltip>
         ) : (
            <Space orientation="vertical" size={0}>
               <Text strong>{col.name}</Text>
               <Text type="secondary" style={{ fontSize: "10px" }}>
                  {col.type}
               </Text>
            </Space>
         ),
         dataIndex: col.name,
         key: col.name,
         width: compact ? 120 : 150,
         ellipsis: {
            showTitle: false
         },
         render: (value: unknown) => {
            if (value === null || value === undefined) {
               return (
                  <Text
                     type="secondary"
                     style={{ fontSize: compact ? "11px" : "12px" }}
                  >
                     NULL
                  </Text>
               );
            }

            // Handle different data types
            if (typeof value === "object") {
               return (
                  <Text
                     style={{
                        fontSize: compact ? "11px" : "12px",
                        fontFamily: "monospace"
                     }}
                     ellipsis={{ tooltip: JSON.stringify(value, null, 2) }}
                  >
                     {JSON.stringify(value)}
                  </Text>
               );
            }

            // Handle boolean values
            if (typeof value === "boolean") {
               return (
                  <Text style={{ fontSize: compact ? "11px" : "12px" }}>
                     {value ? "true" : "false"}
                  </Text>
               );
            }

            // Handle numbers
            if (typeof value === "number") {
               return (
                  <Text style={{ fontSize: compact ? "11px" : "12px" }}>
                     {value.toLocaleString()}
                  </Text>
               );
            }

            // Handle strings and other values
            const stringValue = String(value);
            return (
               <Text
                  ellipsis={{
                     tooltip: stringValue.length > 50 ? stringValue : false
                  }}
                  style={{ fontSize: compact ? "11px" : "12px" }}
               >
                  {stringValue}
               </Text>
            );
         }
      }));
   }, [columns, compact]);

   return (
      <Table
         columns={tableColumns}
         dataSource={tableData}
         loading={loading}
         locale={{
            emptyText: (
               <Empty
                  image={Empty.PRESENTED_IMAGE_SIMPLE}
                  description="No results found"
               />
            )
         }}
         pagination={{
            size: "small",
            hideOnSinglePage: true,
            showSizeChanger: !compact,
            showQuickJumper: !compact,
            pageSizeOptions: PAGE_SIZE_OPTIONS,
            showTotal: (total, range) =>
               compact
                  ? `${range[0]}-${range[1]} of ${total}`
                  : `${range[0]}-${range[1]} of ${total} rows`
         }}
         scroll={{
            x: compact
               ? Math.max(400, (columns?.length || 0) * 120)
               : Math.max(800, (columns?.length || 0) * 150),
            y: compact ? undefined : "calc(100vh - 300px)"
         }}
         size="small"
         rowKey={(record) => record._rowIndex as number}
      />
   );
};

export default QueryResultsTable;
