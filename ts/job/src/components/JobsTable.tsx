import { formatTimeAgo } from "@kontext-tech/common/utils";
import { UserAvatarById } from "@kontext-tech/identity";
import { CheckCircleOutlined, CloseCircleOutlined } from "@kontext-tech/icons";
import type { JobModel, UnifiedJobTypeModel } from "@kontext-tech/schema";
import { Descriptions, Space, Table, Tooltip, Typography, theme } from "antd";
import type { ColumnsType } from "antd/es/table";
import cronstrue from "cronstrue";
import React from "react";
import type { JobActionsProps } from "../jobTypes";
import JobActions from "./JobActions";
import JobRunStats from "./JobRunStats";
import RuntimeBadge from "./RuntimeBadge";

interface JobsTableProps {
   jobs: JobModel[];
   jobTypes: UnifiedJobTypeModel[];
   loading: boolean;
   pagination: {
      current: number;
      pageSize: number;
      total: number;
   };
   onPaginationChange: (page: number, pageSize: number) => void;
   jobActions: Omit<JobActionsProps, "job">;
   pageSizeOptions: string[];
}

const JobsTable: React.FC<JobsTableProps> = ({
   jobs,
   jobTypes,
   loading,
   pagination,
   onPaginationChange,
   jobActions,
   pageSizeOptions
}) => {
   const { token } = theme.useToken();

   const columns: ColumnsType<JobModel> = [
      {
         title: "Name",
         dataIndex: "name",
         key: "name",
         ellipsis: true,
         render: (text: string, record: JobModel) => {
            const isQueryJob = record.type === "python.jobs.ExecuteQueryJob";
            let displayName = text;
            let tooltipContent = record.projectName
               ? `${text} (${record.projectName})`
               : text;

            if (isQueryJob && record.parameters) {
               try {
                  const params = JSON.parse(record.parameters);
                  if (params.query) {
                     displayName = params.query;
                     tooltipContent = params.query;
                  }
               } catch {
                  // Fallback
               }
            }

            return <Tooltip title={tooltipContent}>{displayName}</Tooltip>;
         }
      },
      {
         title: "Job Type",
         dataIndex: "type",
         key: "type",
         ellipsis: true,
         width: 180,
         render: (jobType: string) => {
            const jobTypeInfo = jobTypes.find((item) => item.type === jobType);
            return (
               <Space orientation="vertical" size="small">
                  <Tooltip title={jobTypeInfo?.description}>
                     <span>{jobTypeInfo?.name || jobType}</span>
                  </Tooltip>
                  {jobTypeInfo?.runtime && (
                     <RuntimeBadge runtime={jobTypeInfo.runtime} size="small" />
                  )}
               </Space>
            );
         }
      },
      {
         title: "Owner",
         dataIndex: "ownerId",
         key: "ownerId",
         ellipsis: true,
         width: 120,
         render: (ownerId: string | null) =>
            ownerId ? (
               <UserAvatarById
                  userId={ownerId}
                  showTooltip
                  tooltipText="Owner"
               />
            ) : (
               <Typography.Text type="secondary">System</Typography.Text>
            )
      },
      {
         title: "Enabled",
         dataIndex: "isEnabled",
         key: "isEnabled",
         width: 100,
         render: (isEnabled: boolean) => (
            <Tooltip title={isEnabled ? "Job is enabled" : "Job is disabled"}>
               {isEnabled ? (
                  <CheckCircleOutlined style={{ color: token.colorSuccess }} />
               ) : (
                  <CloseCircleOutlined style={{ color: token.colorError }} />
               )}
            </Tooltip>
         )
      },
      {
         title: "Run Statistics",
         key: "runStats",
         width: 200,
         render: (_, record: JobModel) => (
            <JobRunStats
               totalRuns={record.totalRuns || 0}
               successfulRuns={record.successfulRuns || 0}
               failedRuns={record.failedRuns || 0}
               inProgressRuns={record.inProgressRuns || 0}
            />
         )
      },
      {
         title: "Schedule",
         dataIndex: "schedule",
         key: "status",
         width: 100,
         render: (schedule: string) => {
            if (schedule) {
               return (
                  <Tooltip title={cronstrue.toString(schedule)}>
                     Scheduled
                  </Tooltip>
               );
            }
            return "-";
         }
      },
      {
         title: "Actions",
         key: "actions",
         render: (_, record: JobModel) => (
            <JobActions
               key={`job-actions-${record.id}`}
               job={record}
               {...jobActions}
            />
         ),
         width: 180,
         fixed: "right"
      }
   ];

   const expandedRowRender = (record: JobModel) => {
      const jobTypeInfo = jobTypes.find((item) => item.type === record.type);

      return (
         <Descriptions
            size="small"
            column={{ xs: 1, sm: 2, md: 2, lg: 3, xl: 3 }}
            bordered
         >
            <Descriptions.Item label="Job ID">
               <Typography.Text copyable>{record.id}</Typography.Text>
            </Descriptions.Item>
            <Descriptions.Item label="Job Type Details">
               {jobTypeInfo?.description || "No description available"}
            </Descriptions.Item>
            <Descriptions.Item label="Schedule">
               {record.schedule ? (
                  <Tooltip title={cronstrue.toString(record.schedule)}>
                     {record.schedule}
                  </Tooltip>
               ) : (
                  "N/A"
               )}
            </Descriptions.Item>
            <Descriptions.Item label="Project">
               {record.projectName || "Global"}
            </Descriptions.Item>
            <Descriptions.Item label="Owner">
               {record.ownerId ? (
                  <UserAvatarById
                     userId={record.ownerId}
                     showTooltip
                     tooltipText="Owner"
                  />
               ) : (
                  <Typography.Text type="secondary">System</Typography.Text>
               )}
            </Descriptions.Item>
            <Descriptions.Item label="Created">
               {record.dateCreated ? (
                  <Tooltip title={record.dateCreated.toString()}>
                     {formatTimeAgo(record.dateCreated)}
                  </Tooltip>
               ) : (
                  "N/A"
               )}
            </Descriptions.Item>
            <Descriptions.Item label="Last Run">
               {record.lastRunDate ? (
                  <Tooltip title={record.lastRunDate.toString()}>
                     {formatTimeAgo(record.lastRunDate)}
                  </Tooltip>
               ) : (
                  "Never"
               )}
            </Descriptions.Item>
            <Descriptions.Item label="Description">
               {record.description || "No description"}
            </Descriptions.Item>
            <Descriptions.Item label="Parameters">
               {record.parameters ? (
                  <pre>{record.parameters}</pre>
               ) : (
                  "No parameters"
               )}
            </Descriptions.Item>
         </Descriptions>
      );
   };

   return (
      <Table
         columns={columns}
         dataSource={jobs}
         rowKey="id"
         loading={loading}
         scroll={{ x: 600 }}
         expandable={{
            expandedRowRender,
            rowExpandable: () => true,
            defaultExpandAllRows: false
         }}
         pagination={{
            hideOnSinglePage: true,
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: pagination.total,
            showSizeChanger: true,
            pageSizeOptions,
            showQuickJumper: true,
            showTotal: (total, range) =>
               `${range[0]}-${range[1]} of ${total} jobs`,
            onChange: onPaginationChange
         }}
      />
   );
};

export default JobsTable;
