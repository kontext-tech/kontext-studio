import { formatDuration, formatTimeAgo } from "@kontext-labs/common";
import type { QueryModel } from "@kontext-labs/schema";
import { Empty, Spin, Table, Tag, Typography, theme } from "antd";
import type { ColumnsType } from "antd/es/table";
import React, { useCallback, useEffect, useState } from "react";
import { useProjectQuerySessions } from "../hooks/useQuerySessions";
import {
   ClockCircleOutlined,
   DownOutlined,
   RightOutlined
} from "@kontext-labs/icons";

const { Text } = Typography;

interface QueryHistoryTabProps {
   projectId: string;
   sessionId: string;
   refreshTrigger?: number;
}

const QueryHistoryTab: React.FC<QueryHistoryTabProps> = ({
   projectId,
   sessionId,
   refreshTrigger
}) => {
   const { token } = theme.useToken();
   const { getQueries } = useProjectQuerySessions(projectId);

   const [queries, setQueries] = useState<QueryModel[]>([]);
   const [isLoading, setIsLoading] = useState<boolean>(false);
   const [error, setError] = useState<string | null>(null);

   const fetchQueries = useCallback(async () => {
      if (!sessionId) return;

      setIsLoading(true);
      setError(null);

      try {
         const result = await getQueries(sessionId);
         if (result) {
            setQueries(result);
         } else {
            setError("Failed to load query history");
         }
      } catch (err) {
         setError("An unexpected error occurred while loading query history");
         console.error("Error fetching query history:", err);
      } finally {
         setIsLoading(false);
      }
   }, [sessionId, getQueries]);

   useEffect(() => {
      const timeoutId = window.setTimeout(() => {
         void fetchQueries();
      }, 0);

      return () => window.clearTimeout(timeoutId);
   }, [fetchQueries, refreshTrigger]);

   const getStatusText = (succeeded: boolean, hasError: boolean) => {
      if (hasError) return "Failed";
      if (succeeded) return "Success";
      return "Running";
   };

   const getStatusColor = (succeeded: boolean, hasError: boolean) => {
      if (hasError) return "error";
      if (succeeded) return "success";
      return "warning";
   };

   // Use compact duration formatting in the table

   const columns: ColumnsType<QueryModel> = [
      {
         title: "Query",
         dataIndex: "id",
         key: "query",
         render: (_, _record, index) => (
            <Text strong style={{ fontSize: token.fontSizeSM }}>
               Query #{queries.length - index}
            </Text>
         ),
         width: 100
      },
      {
         title: "Status",
         dataIndex: "succeeded",
         key: "status",
         render: (succeeded, query) => (
            <Tag color={getStatusColor(succeeded || false, !!query.message)}>
               {getStatusText(succeeded || false, !!query.message)}
            </Tag>
         ),
         width: 100
      },
      {
         title: "Results",
         dataIndex: "recordCount",
         key: "results",
         render: (recordCount) =>
            recordCount !== undefined &&
            recordCount !== null &&
            recordCount > 0 ? (
               <Text type="secondary" style={{ fontSize: token.fontSizeSM }}>
                  {recordCount} row{recordCount !== 1 ? "s" : ""}
               </Text>
            ) : (
               "-"
            ),
         width: 100
      },
      {
         title: "Executed",
         dataIndex: "createdAt",
         key: "executed",
         render: (createdAt) => (
            <Text type="secondary" style={{ fontSize: token.fontSizeSM }}>
               <ClockCircleOutlined style={{ marginRight: 4 }} />
               {createdAt ? formatTimeAgo(createdAt) : "Unknown"}
            </Text>
         ),
         width: 150
      },
      {
         title: "Duration",
         dataIndex: "durationMs",
         key: "duration",
         render: (durationMs) => (
            <Text type="secondary" style={{ fontSize: token.fontSizeSM }}>
               {formatDuration(durationMs, true)}
            </Text>
         ),
         width: 100
      }
   ];

   const expandedRowRender = (query: QueryModel) => (
      <div style={{ padding: token.paddingMD }}>
         {/* Query Code */}
         <div style={{ marginBottom: token.marginMD }}>
            <Text
               strong
               style={{ display: "block", marginBottom: token.marginXS }}
            >
               Query Code:
            </Text>
            <Text
               code
               copyable
               style={{
                  margin: 0,
                  fontSize: token.fontSizeSM,
                  maxHeight: "300px",
                  overflow: "auto",
                  padding: token.paddingXS
               }}
            >
               {query.code}
            </Text>
         </div>

         {/* Error Message */}
         {query.message && (
            <div>
               <Text
                  strong
                  style={{ display: "block", marginBottom: token.marginXS }}
               >
                  Error Details:
               </Text>
               <Text type="danger" style={{ fontSize: token.fontSizeSM }}>
                  {query.message}
               </Text>
            </div>
         )}
      </div>
   );

   if (isLoading) {
      return (
         <div
            style={{
               display: "flex",
               justifyContent: "center",
               padding: token.paddingLG
            }}
         >
            <Spin size="large" />
         </div>
      );
   }

   if (error) {
      return <Empty description={error} style={{ padding: token.paddingLG }} />;
   }

   if (queries.length === 0) {
      return (
         <Empty
            description="No queries executed yet"
            style={{ padding: token.paddingLG }}
         />
      );
   }

   return (
      <Table
         dataSource={queries}
         columns={columns}
         rowKey={(record) => record.id || `query-${queries.indexOf(record)}`}
         expandable={{
            expandedRowRender,
            expandIcon: ({ expanded, onExpand, record }) =>
               expanded ? (
                  <DownOutlined
                     onClick={(e) => onExpand(record, e)}
                     style={{
                        cursor: "pointer",
                        marginRight: 8,
                        color: token.colorPrimary
                     }}
                  />
               ) : (
                  <RightOutlined
                     onClick={(e) => onExpand(record, e)}
                     style={{
                        cursor: "pointer",
                        marginRight: 8,
                        color: token.colorTextSecondary
                     }}
                  />
               )
         }}
         size="small"
         pagination={false}
         style={{
            height: "100%",
            overflow: "auto"
         }}
         scroll={{ y: "100%" }}
      />
   );
};

export default QueryHistoryTab;
