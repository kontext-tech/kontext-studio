import { UserAvatarById } from "@kontext-tech/identity";
import type { ApiErrorResult } from "@kontext-tech/common";
import { formatFullDateTime, formatTimeAgo } from "@kontext-tech/common";
import {
   DeleteOutlined,
   ReloadOutlined,
   StopOutlined
} from "@kontext-tech/icons";
import { useDataService } from "@kontext-tech/app-runtime/hooks";
import type { QuerySessionModel } from "@kontext-tech/schema";
import { QuerySessionStatus } from "@kontext-tech/schema";
import { Button, Modal, Space, Table, Tag, Tooltip, Typography } from "antd";
import type { ColumnsType } from "antd/es/table";
import React, { useCallback, useEffect, useState } from "react";
import { QuerySessionService } from "../QuerySessionService";

const { Text } = Typography;

export interface ProjectQuerySessionsPanelProps {
   projectId: string;
   errorHandler?: (error: ApiErrorResult) => Promise<void>;
   onMessage?: (
      type: "success" | "error" | "warning" | "info",
      content: string
   ) => void;
}

export const ProjectQuerySessionsPanel: React.FC<
   ProjectQuerySessionsPanelProps
> = ({ projectId, errorHandler, onMessage }) => {
   const [sessions, setSessions] = useState<QuerySessionModel[]>([]);
   const [loading, setLoading] = useState(false);
   const [currentPage, setCurrentPage] = useState(1);
   const [pageSize, setPageSize] = useState(10);
   const [totalCount, setTotalCount] = useState(0);
   const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);

   const querySessionService = useDataService(
      QuerySessionService,
      errorHandler
   );

   const fetchSessions = useCallback(
      async (page: number = currentPage, size: number = pageSize) => {
         setLoading(true);
         try {
            const result = await querySessionService.listSessions(
               projectId,
               page,
               size
            );

            if (result.succeed && result.data) {
               setSessions(result.data.items || []);
               setTotalCount(result.data.totalCount || 0);
            } else {
               onMessage?.(
                  "error",
                  result.error?.title || "Failed to load sessions"
               );
            }
         } catch (error) {
            console.error("Error fetching sessions:", error);
            onMessage?.(
               "error",
               "An unexpected error occurred while fetching sessions"
            );
         } finally {
            setLoading(false);
         }
      },
      [currentPage, onMessage, pageSize, projectId, querySessionService]
   );

   useEffect(() => {
      const timeoutId = window.setTimeout(() => {
         void fetchSessions();
      }, 0);

      return () => window.clearTimeout(timeoutId);
   }, [fetchSessions]);

   const handleDelete = (sessionId: string) => {
      Modal.confirm({
         title: "Delete Session",
         content:
            "Are you sure you want to delete this session? This will permanently remove the session and its data.",
         okText: "Yes",
         okType: "danger",
         cancelText: "No",
         onOk: async () => {
            try {
               const result = await querySessionService.closeSession(
                  projectId,
                  sessionId
               );
               if (result.succeed) {
                  onMessage?.("success", "Session deleted successfully");
                  void fetchSessions();
               } else {
                  onMessage?.(
                     "error",
                     result.error?.title || "Failed to delete session"
                  );
               }
            } catch (error) {
               console.error("Error deleting session:", error);
               onMessage?.(
                  "error",
                  "An unexpected error occurred while deleting the session"
               );
            }
         }
      });
   };

   const handleStop = (sessionId: string) => {
      Modal.confirm({
         title: "Stop Session",
         content: "Are you sure you want to stop this session?",
         okText: "Yes",
         cancelText: "No",
         onOk: async () => {
            try {
               const result = await querySessionService.updateSession(
                  projectId,
                  sessionId,
                  { status: QuerySessionStatus.Closed }
               );
               if (result.succeed) {
                  onMessage?.("success", "Session stopped successfully");
                  void fetchSessions();
               } else {
                  onMessage?.(
                     "error",
                     result.error?.title || "Failed to stop session"
                  );
               }
            } catch (error) {
               console.error("Error stopping session:", error);
               onMessage?.(
                  "error",
                  "An unexpected error occurred while stopping the session"
               );
            }
         }
      });
   };

   const handleBulkDelete = () => {
      if (selectedRowKeys.length === 0) return;

      Modal.confirm({
         title: "Delete Multiple Sessions",
         content: `Are you sure you want to delete ${selectedRowKeys.length} selected sessions? This will permanently remove the sessions and their data.`,
         okText: "Yes",
         okType: "danger",
         cancelText: "No",
         onOk: async () => {
            setLoading(true);
            try {
               const results = await Promise.all(
                  selectedRowKeys.map((id) =>
                     querySessionService.closeSession(projectId, id as string)
                  )
               );
               const failedCount = results.filter(
                  (result: { succeed: boolean }) => !result.succeed
               ).length;

               if (failedCount === 0) {
                  onMessage?.(
                     "success",
                     `Successfully deleted ${selectedRowKeys.length} sessions`
                  );
               } else {
                  onMessage?.(
                     "warning",
                     `Deleted ${selectedRowKeys.length - failedCount} sessions, but ${failedCount} failed`
                  );
               }

               setSelectedRowKeys([]);
               void fetchSessions();
            } catch (error) {
               console.error("Error deleting multiple sessions:", error);
               onMessage?.(
                  "error",
                  "An unexpected error occurred during bulk delete"
               );
            } finally {
               setLoading(false);
            }
         }
      });
   };

   const handleBulkStop = () => {
      if (selectedRowKeys.length === 0) return;

      Modal.confirm({
         title: "Stop Multiple Sessions",
         content: `Are you sure you want to stop ${selectedRowKeys.length} selected sessions?`,
         okText: "Yes",
         cancelText: "No",
         onOk: async () => {
            setLoading(true);
            try {
               const results = await Promise.all(
                  selectedRowKeys.map((id) =>
                     querySessionService.updateSession(
                        projectId,
                        id as string,
                        {
                           status: QuerySessionStatus.Closed
                        }
                     )
                  )
               );
               const failedCount = results.filter(
                  (result: { succeed: boolean }) => !result.succeed
               ).length;

               if (failedCount === 0) {
                  onMessage?.(
                     "success",
                     `Successfully stopped ${selectedRowKeys.length} sessions`
                  );
               } else {
                  onMessage?.(
                     "warning",
                     `Stopped ${selectedRowKeys.length - failedCount} sessions, but ${failedCount} failed`
                  );
               }

               setSelectedRowKeys([]);
               void fetchSessions();
            } catch (error) {
               console.error("Error stopping multiple sessions:", error);
               onMessage?.(
                  "error",
                  "An unexpected error occurred during bulk stop"
               );
            } finally {
               setLoading(false);
            }
         }
      });
   };

   const getStatusTag = (status: QuerySessionStatus) => {
      switch (status) {
         case QuerySessionStatus.Active:
            return <Tag color="success">Active</Tag>;
         case QuerySessionStatus.Initializing:
            return <Tag color="processing">Initializing</Tag>;
         case QuerySessionStatus.Error:
            return <Tag color="error">Error</Tag>;
         case QuerySessionStatus.Closed:
            return <Tag color="default">Closed</Tag>;
         case QuerySessionStatus.Deleted:
            return <Tag color="warning">Deleted</Tag>;
         default:
            return <Tag>{status}</Tag>;
      }
   };

   const columns: ColumnsType<QuerySessionModel> = [
      {
         title: "Session Name",
         dataIndex: "sessionName",
         key: "sessionName",
         render: (text: string) => <Text strong>{text}</Text>
      },
      {
         title: "Status",
         dataIndex: "status",
         key: "status",
         render: (status: QuerySessionStatus) => getStatusTag(status)
      },
      {
         title: "Owner",
         dataIndex: "ownerId",
         key: "ownerId",
         render: (ownerId: string) => (
            <UserAvatarById
               userId={ownerId}
               size="default"
               showTooltip={true}
               tooltipText={`Owner: ${ownerId}`}
            />
         )
      },
      {
         title: "Created At",
         dataIndex: "createdAt",
         key: "createdAt",
         render: (date: string) => (
            <Text type="secondary" title={formatFullDateTime(date)}>
               {formatTimeAgo(date)}
            </Text>
         )
      },
      {
         title: "Last Accessed",
         dataIndex: "lastAccessedAt",
         key: "lastAccessedAt",
         render: (date: string) =>
            date ? (
               <Text type="secondary" title={formatFullDateTime(date)}>
                  {formatTimeAgo(date)}
               </Text>
            ) : (
               "-"
            )
      },
      {
         title: "Actions",
         key: "actions",
         render: (_, record) => {
            const isDeleted = record.status === QuerySessionStatus.Deleted;
            const isActive = record.status === QuerySessionStatus.Active;

            return (
               <Space size="middle">
                  {isActive && (
                     <Tooltip title="Stop Session">
                        <Button
                           type="text"
                           icon={<StopOutlined />}
                           onClick={() => record.id && handleStop(record.id)}
                        />
                     </Tooltip>
                  )}
                  <Tooltip
                     title={
                        isDeleted ? "Session already deleted" : "Delete Session"
                     }
                  >
                     <Button
                        type="text"
                        danger
                        icon={<DeleteOutlined />}
                        disabled={isDeleted}
                        onClick={() => record.id && handleDelete(record.id)}
                     />
                  </Tooltip>
               </Space>
            );
         }
      }
   ];

   return (
      <Space orientation="vertical" size="middle" style={{ width: "100%" }}>
         <Space>
            <Button
               icon={<ReloadOutlined />}
               onClick={() => void fetchSessions()}
               loading={loading}
            >
               Refresh
            </Button>
            {selectedRowKeys.length > 0 && (
               <>
                  <Button
                     icon={<StopOutlined />}
                     onClick={handleBulkStop}
                     disabled={loading}
                  >
                     Stop Selected ({selectedRowKeys.length})
                  </Button>
                  <Button
                     danger
                     icon={<DeleteOutlined />}
                     onClick={handleBulkDelete}
                     disabled={loading}
                  >
                     Delete Selected ({selectedRowKeys.length})
                  </Button>
               </>
            )}
         </Space>
         <Table
            rowSelection={{
               selectedRowKeys,
               onChange: (keys) => setSelectedRowKeys(keys)
            }}
            columns={columns}
            dataSource={sessions}
            rowKey="id"
            loading={loading}
            pagination={{
               current: currentPage,
               pageSize,
               total: totalCount,
               onChange: (page, size) => {
                  setCurrentPage(page);
                  setPageSize(size);
                  void fetchSessions(page, size);
               },
               showSizeChanger: true
            }}
         />
      </Space>
   );
};
