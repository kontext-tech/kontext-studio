import { PAGE_SIZE_OPTIONS } from "@kontext-tech/common";
import { formatFullDateTime, formatTimeAgo } from "@kontext-tech/common/utils";
import { UserAvatarById } from "@kontext-tech/identity";
import type {
   JobModel,
   JobRunModel,
   JobRunStatus,
   TriggerActorModel,
   UnifiedJobTypeModel
} from "@kontext-tech/schema";
import { Table, Tag, Typography, type TablePaginationConfig } from "antd";
import type { ColumnsType } from "antd/es/table";
import React, { type ReactNode } from "react";
import type { JobRunActionsProps } from "../jobTypes";
import {
   getJobRunDuration,
   getJobRunStatusInfo,
   getTriggerActorLabel
} from "../utils";
import JobRunActions from "./JobRunActions";
import JobRunProgress from "./JobRunProgress";

const { Text } = Typography;

interface JobRunsTableProps {
   jobRuns: JobRunModel[];
   jobTypes: UnifiedJobTypeModel[];
   loading: boolean;
   pagination: {
      current: number;
      pageSize: number;
      total: number;
   };
   onTableChange: (pagination: TablePaginationConfig) => void;
   jobRunActions: Omit<JobRunActionsProps, "jobRun">;
   renderTriggerActor?: (actor: TriggerActorModel) => ReactNode;
}

const JobRunsTable: React.FC<JobRunsTableProps> = ({
   jobRuns,
   jobTypes,
   loading,
   pagination,
   onTableChange,
   jobRunActions,
   renderTriggerActor
}) => {
   const columns: ColumnsType<JobRunModel> = [
      {
         title: "Job",
         dataIndex: "job",
         key: "job",
         render: (job: JobModel | null | undefined, record: JobRunModel) => {
            const jobName = job?.name || "Unknown Job";
            const summary = record.displaySummary;
            const jobTypeName =
               jobTypes.find((item) => item.type === job?.type)?.name ||
               jobName;
            const displayName = summary || jobName;
            // Tooltip stays light: no full SQL/code payloads, only the
            // human job name (the code itself is visible in run details).
            const tooltipContent = jobName;

            return (
               <>
                  <Text strong ellipsis={{ tooltip: tooltipContent }}>
                     {displayName}
                  </Text>
                  {record.executionId && (
                     <>
                        <Text type="secondary"> - </Text>
                        <Text type="secondary">{record.executionId}</Text>
                     </>
                  )}
                  {jobTypeName && (
                     <Text
                        type="secondary"
                        style={{ display: "block", fontSize: 12 }}
                        ellipsis={{ tooltip: jobTypeName }}
                     >
                        {jobTypeName}
                     </Text>
                  )}
               </>
            );
         },
         ellipsis: { showTitle: true }
      },
      {
         title: "Status",
         dataIndex: "status",
         key: "status",
         render: (status: JobRunStatus) => {
            const statusInfo = getJobRunStatusInfo(status);
            return <Tag color={statusInfo.color}>{statusInfo.name}</Tag>;
         },
         width: 120
      },
      {
         title: "User",
         key: "user",
         render: (_, record) => {
            const actor = record.jobTrigger?.triggeredBy;
            let userId = record.job?.ownerId || record.ownerId;

            if (actor?.type === "User" && actor.id) {
               userId = actor.id;
            }

            return userId ? (
               <UserAvatarById
                  userId={userId}
                  showTooltip
                  tooltipText={getTriggerActorLabel(actor) || "User"}
               />
            ) : (
               <Text type="secondary">—</Text>
            );
         },
         width: 80
      },
      {
         title: "Progress",
         dataIndex: "progress",
         key: "progress",
         render: (progress: number, record: JobRunModel) =>
            progress != null ? (
               <JobRunProgress progress={progress} status={record.status} />
            ) : (
               "-"
            ),
         width: 120
      },
      {
         title: "Started",
         dataIndex: "startedAt",
         key: "startedAt",
         render: (date: string) =>
            date ? (
               <Text type="secondary" title={formatFullDateTime(date)}>
                  {formatTimeAgo(date)}
               </Text>
            ) : (
               "-"
            ),
         width: 140
      },
      {
         title: "Duration",
         key: "duration",
         render: (_, record) =>
            getJobRunDuration(
               record.startedAt ? new Date(record.startedAt) : null,
               record.completedAt ? new Date(record.completedAt) : null
            ),
         width: 100
      },
      {
         title: "Triggered By",
         key: "triggeredBy",
         render: (_, record) => {
            const actor = record.jobTrigger?.triggeredBy;
            if (!actor) {
               return "-";
            }

            const label = getTriggerActorLabel(actor) || "-";
            const content = renderTriggerActor
               ? renderTriggerActor(actor)
               : label;

            return (
               <Text
                  style={{ maxWidth: "140px" }}
                  ellipsis={{ tooltip: label }}
               >
                  {content}
               </Text>
            );
         },
         width: 140
      },
      {
         title: "Actions",
         key: "actions",
         render: (_, record) => (
            <JobRunActions jobRun={record} {...jobRunActions} />
         ),
         width: 100,
         fixed: "right"
      }
   ];

   return (
      <Table
         columns={columns}
         dataSource={jobRuns}
         rowKey="id"
         loading={loading}
         pagination={{
            hideOnSinglePage: true,
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: pagination.total,
            showSizeChanger: true,
            showQuickJumper: true,
            pageSizeOptions: PAGE_SIZE_OPTIONS,
            showTotal: (total, range) =>
               `${range[0]}-${range[1]} of ${total} job runs`
         }}
         onChange={onTableChange}
         scroll={{ x: 1000 }}
      />
   );
};

export default JobRunsTable;
