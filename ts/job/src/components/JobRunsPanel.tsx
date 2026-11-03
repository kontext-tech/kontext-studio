import type { ApiErrorResult } from "@kontext-labs/common";
import { ReloadOutlined } from "@kontext-labs/icons";
import type {
   JobRunModel,
   JobRunStatus,
   TriggerActorModel
} from "@kontext-labs/schema";
import type { UiFeedback } from "@kontext-labs/ui";
import type { TablePaginationConfig } from "antd";
import { Alert, Button, Select, Space } from "antd";
import React, { useState, type ReactNode } from "react";
import { useDataJobRuns } from "../useDataJobRuns";
import { useDataJobTypes } from "../useDataJobTypes";
import EditParametersModal from "./EditParametersModal";
import JobRunDetailsDrawer from "./JobRunDetailsDrawer";
import JobRunsTable from "./JobRunsTable";

export interface JobRunsPanelProps {
   projectId: string;
   selectedRunId?: string | null;
   onSelectedRunIdChange?: (runId: string | null) => void;
   errorHandler?: (error: ApiErrorResult) => Promise<void>;
   ui: UiFeedback;
   renderTriggerActor?: (actor: TriggerActorModel) => ReactNode;
}

export const JobRunsPanel: React.FC<JobRunsPanelProps> = ({
   projectId,
   selectedRunId: controlledSelectedRunId,
   onSelectedRunIdChange,
   errorHandler,
   ui,
   renderTriggerActor
}) => {
   const isSelectedRunIdControlled = controlledSelectedRunId !== undefined;
   const { fetchJobParametersByType, jobTypes } = useDataJobTypes(
      projectId,
      errorHandler
   );
   const {
      jobRuns,
      totalCount,
      loading,
      error,
      pageIndex,
      pageSize,
      status,
      setPageIndex,
      setPageSize,
      setStatus,
      loadJobRuns,
      getJobRun,
      getJobRunLogs,
      resetJobRuns,
      cancelJobRun
   } = useDataJobRuns(projectId, errorHandler);

   const [uncontrolledSelectedRunId, setUncontrolledSelectedRunId] = useState<
      string | null
   >(null);
   const selectedRunId = isSelectedRunIdControlled
      ? controlledSelectedRunId
      : uncontrolledSelectedRunId;
   const [editParametersModal, setEditParametersModal] = useState<{
      open: boolean;
      jobRun: JobRunModel | null;
   }>({
      open: false,
      jobRun: null
   });

   const pagination = {
      current: pageIndex,
      pageSize,
      total: totalCount
   };

   const handleTableChange = (newPagination: TablePaginationConfig) => {
      setPageIndex(newPagination.current || 1);
      setPageSize(newPagination.pageSize || 10);
   };

   const handleStatusChange = (value: JobRunStatus | undefined) => {
      setStatus(value);
      setPageIndex(1);
   };

   const clearFilters = () => {
      setStatus(undefined);
      setPageIndex(1);
   };

   const updateSelectedRunId = (runId: string | null) => {
      if (!isSelectedRunIdControlled) {
         setUncontrolledSelectedRunId(runId);
      }

      onSelectedRunIdChange?.(runId);
   };

   const viewJobRunDetails = (runId: string) => {
      updateSelectedRunId(runId);
   };

   const closeJobRunDetails = () => {
      updateSelectedRunId(null);
   };

   const handleEditParameters = async (runId: string) => {
      const jobRun = jobRuns.find((run) => run.id === runId);

      if (jobRun) {
         setEditParametersModal({
            open: true,
            jobRun
         });
      } else {
         ui.error("Could not find job run details");
      }
   };

   const handleCancel = async (runId: string, jobName: string) => {
      const confirmed = await new Promise<boolean>((resolve) => {
         ui.confirm({
            title: "Cancel run",
            content: `Cancel "${jobName}"? In-flight work is stopped.`,
            okText: "Cancel run",
            okButtonProps: { danger: true },
            cancelText: "Keep running",
            onOk: () => resolve(true),
            onCancel: () => resolve(false)
         });
      });

      if (!confirmed) {
         return;
      }

      const success = await cancelJobRun(runId);
      if (success) {
         ui.success("Run cancelled");
      } else {
         ui.error("Failed to cancel run");
      }
   };

   const handleCloseEditParametersModal = () => {
      setEditParametersModal({
         open: false,
         jobRun: null
      });
   };

   return (
      <Space orientation="vertical" size="large" style={{ width: "100%" }}>
         <Space wrap>
            <Select
               placeholder="Filter by status"
               allowClear
               style={{ width: 150 }}
               value={status}
               onChange={handleStatusChange}
               options={[
                  { label: "Pending", value: "Pending" },
                  { label: "Running", value: "Running" },
                  { label: "Completed", value: "Completed" },
                  { label: "Failed", value: "Failed" },
                  { label: "Cancelled", value: "Cancelled" }
               ]}
            />
            <Button onClick={clearFilters}>Clear Filters</Button>
            <Button
               icon={<ReloadOutlined />}
               loading={loading}
               onClick={() => void loadJobRuns()}
            >
               Refresh
            </Button>
         </Space>

         {error && (
            <Alert
               title="Error Loading Job Runs"
               description={error}
               type="error"
               closable
               style={{ marginBottom: "16px" }}
            />
         )}

         <JobRunsTable
            jobRuns={jobRuns}
            jobTypes={jobTypes}
            loading={loading}
            pagination={pagination}
            onTableChange={handleTableChange}
            jobRunActions={{
               onViewDetails: viewJobRunDetails,
               onEditParameters: handleEditParameters,
               onCancel: handleCancel,
               ui
            }}
            renderTriggerActor={renderTriggerActor}
         />

         <JobRunDetailsDrawer
            open={!!selectedRunId}
            selectedRunId={selectedRunId}
            fetchJobParametersByType={fetchJobParametersByType}
            getJobRun={getJobRun}
            getJobRunLogs={getJobRunLogs}
            resetJobRuns={resetJobRuns}
            cancelJobRun={cancelJobRun}
            ui={ui}
            onClose={closeJobRunDetails}
            onJobRunReset={() => void loadJobRuns()}
            renderTriggerActor={renderTriggerActor}
         />

         <EditParametersModal
            open={editParametersModal.open}
            jobRun={editParametersModal.jobRun}
            fetchJobParametersByType={fetchJobParametersByType}
            ui={ui}
            onClose={handleCloseEditParametersModal}
            onSuccess={() => void loadJobRuns()}
         />
      </Space>
   );
};
