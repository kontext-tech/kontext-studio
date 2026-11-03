import { PermissionButton } from "@kontext-labs/auth";
import { PERMISSION_CLAIMS } from "@kontext-labs/auth";
import { LoadingSpinner } from "@kontext-labs/ui";
import type { UiFeedback } from "@kontext-labs/ui";
import {
   ExclamationCircleOutlined,
   OrderedListOutlined,
   ProfileOutlined,
   ReloadOutlined,
   SettingOutlined
} from "@kontext-labs/icons";
import type {
   JobRunLogModel,
   JobRunModel,
   TriggerActorModel
} from "@kontext-labs/schema";
import { JobRunStatus, JobTriggerType } from "@kontext-labs/schema";
import {
   Alert,
   Button,
   Card,
   Descriptions,
   Drawer,
   Flex,
   Input,
   Modal,
   Space,
   Tabs,
   Tag,
   Typography,
   type TabsProps
} from "antd";
import dayjs from "dayjs";
import React, {
   useCallback,
   useEffect,
   useMemo,
   useRef,
   useState,
   type ReactNode
} from "react";
import type { FetchJobParametersByTypeFn } from "../jobTypes";
import {
   getJobRunDuration,
   getJobRunStatusInfo,
   getJobTriggerTypeName,
   getTriggerActorLabel
} from "../utils";
import JobParameterDisplay from "./JobParameterDisplay";
import JobRunLogsList from "./JobRunLogsList";
import JobRunProgress from "./JobRunProgress";

const { Text, Paragraph } = Typography;

export type GetJobRunFn = (runId: string) => Promise<JobRunModel | null>;

export type GetJobRunLogsFn = (
   runId: string,
   limit?: number
) => Promise<JobRunLogModel[]>;

export type ResetJobRunsFn = (
   jobRunIds: string[],
   reason: string
) => Promise<{ message?: string; resetCount?: number } | null | undefined>;

export type CancelJobRunFn = (runId: string) => Promise<boolean>;

interface JobRunDetailsDrawerProps {
   open: boolean;
   selectedRunId: string | null;
   fetchJobParametersByType?: FetchJobParametersByTypeFn;
   getJobRun: GetJobRunFn;
   getJobRunLogs: GetJobRunLogsFn;
   resetJobRuns?: ResetJobRunsFn;
   cancelJobRun?: CancelJobRunFn;
   ui: UiFeedback;
   onClose: () => void;
   onJobRunReset: () => void;
   renderTriggerActor?: (actor: TriggerActorModel) => ReactNode;
}

const JobRunDetailsDrawer: React.FC<JobRunDetailsDrawerProps> = ({
   open,
   selectedRunId,
   fetchJobParametersByType,
   getJobRun,
   getJobRunLogs,
   resetJobRuns,
   cancelJobRun,
   ui,
   onClose,
   onJobRunReset,
   renderTriggerActor
}) => {
   const [jobRun, setJobRun] = useState<JobRunModel | null>(null);
   const [logs, setLogs] = useState<JobRunLogModel[]>([]);
   const [loading, setLoading] = useState(false);
   const [logsLoading, setLogsLoading] = useState(false);
   const [error, setError] = useState<string | null>(null);
   const [isResetting, setIsResetting] = useState(false);
   const [isCancelling, setIsCancelling] = useState(false);
   const [resetReason, setResetReason] = useState("");
   const [resetModalVisible, setResetModalVisible] = useState(false);
   const [activeTab, setActiveTab] = useState("details");
   const tabsContainerRef = useRef<HTMLDivElement | null>(null);
   const [tabPaneHeight, setTabPaneHeight] = useState<number | null>(null);

   const fetchJobRunData = useCallback(async () => {
      if (!selectedRunId) return;

      setLoading(true);
      setError(null);

      try {
         const result = await getJobRun(selectedRunId);
         if (result) {
            setJobRun(result);
         } else {
            setError("Failed to fetch job run details");
         }
      } catch {
         setError("An unexpected error occurred");
      } finally {
         setLoading(false);
      }
   }, [selectedRunId, getJobRun]);

   const fetchLogs = useCallback(async () => {
      if (!selectedRunId) return;

      setLogsLoading(true);
      try {
         const result = await getJobRunLogs(selectedRunId);
         setLogs(result);
      } catch (loadError) {
         console.error("Failed to fetch logs:", loadError);
      } finally {
         setLogsLoading(false);
      }
   }, [selectedRunId, getJobRunLogs]);

   useEffect(() => {
      const timeoutId = window.setTimeout(() => {
         if (open && selectedRunId) {
            void fetchJobRunData();
            void fetchLogs();
            setActiveTab(
               jobRun?.status === JobRunStatus.Failed ||
                  jobRun?.status === JobRunStatus.TimedOut ||
                  jobRun?.status === JobRunStatus.DeadLettered
                  ? "logs"
                  : "details"
            );
            return;
         }

         setJobRun(null);
         setLogs([]);
         setError(null);
         setActiveTab("details");
      }, 0);

      return () => window.clearTimeout(timeoutId);
   }, [open, selectedRunId, fetchJobRunData, fetchLogs, jobRun?.status]);

   useEffect(() => {
      if (!open || !jobRun) {
         return;
      }

      const container = tabsContainerRef.current;
      if (!container) {
         return;
      }

      let frameId = 0;
      let tabsRootElement: HTMLElement | null = null;
      let tabsNavElement: HTMLElement | null = null;
      let contentHolderElement: HTMLElement | null = null;

      const updatePaneHeight = () => {
         cancelAnimationFrame(frameId);
         frameId = window.requestAnimationFrame(() => {
            tabsRootElement = container.querySelector(".ant-tabs");
            tabsNavElement = container.querySelector(".ant-tabs-nav");
            // antd v6 renamed the scrollable tab panel region from
            // `.ant-tabs-content-holder` to `.ant-tabs-body-holder`. Querying
            // the old class left `tabPaneHeight` null, so the panes never got a
            // bounded height and the drawer could not scroll vertically.
            contentHolderElement = container.querySelector(
               ".ant-tabs-body-holder, .ant-tabs-content-holder"
            );

            if (!(tabsRootElement instanceof HTMLElement)) {
               return;
            }

            if (!(contentHolderElement instanceof HTMLElement)) {
               return;
            }

            const tabsRect = tabsRootElement.getBoundingClientRect();
            const contentHolderRect =
               contentHolderElement.getBoundingClientRect();
            const nextHeight = Math.max(
               0,
               Math.floor(tabsRect.bottom - contentHolderRect.top)
            );

            setTabPaneHeight((currentHeight) =>
               currentHeight === nextHeight ? currentHeight : nextHeight
            );
         });
      };

      updatePaneHeight();

      const resizeObserver = new ResizeObserver(() => {
         updatePaneHeight();
      });

      resizeObserver.observe(container);
      updatePaneHeight();

      if (tabsRootElement) {
         resizeObserver.observe(tabsRootElement);
      }
      if (tabsNavElement) {
         resizeObserver.observe(tabsNavElement);
      }
      if (contentHolderElement) {
         resizeObserver.observe(contentHolderElement);
      }

      window.addEventListener("resize", updatePaneHeight);

      return () => {
         cancelAnimationFrame(frameId);
         resizeObserver.disconnect();
         window.removeEventListener("resize", updatePaneHeight);
      };
   }, [open, jobRun, activeTab, logs.length, logsLoading]);

   const resolvedTabPaneHeight = open && jobRun ? tabPaneHeight : null;

   const scrollableTabPaneStyle = useMemo(
      () => ({
         height: resolvedTabPaneHeight
            ? `${resolvedTabPaneHeight}px`
            : undefined,
         minHeight: 0,
         overflow: "auto",
         paddingRight: 4
      }),
      [resolvedTabPaneHeight]
   );

   const logsTabPaneStyle = useMemo(
      () => ({
         height: resolvedTabPaneHeight
            ? `${resolvedTabPaneHeight}px`
            : undefined,
         minHeight: 0,
         overflow: "hidden"
      }),
      [resolvedTabPaneHeight]
   );

   const handleRefresh = () => {
      fetchJobRunData();
      fetchLogs();
   };

   const statusInfo = getJobRunStatusInfo(jobRun?.status);
   const now = dayjs();
   let dispatchedTooLong = false;
   if (jobRun?.status === JobRunStatus.Dispatched) {
      const dispatchedAt = jobRun.startedAt || jobRun.createdAt;
      if (dispatchedAt) {
         const dispatchedDuration = now.diff(dayjs(dispatchedAt), "minute");
         dispatchedTooLong = dispatchedDuration >= 5;
      }
   }

   const canResetJobRun =
      resetJobRuns &&
      (jobRun?.status === JobRunStatus.Failed ||
         jobRun?.status === JobRunStatus.TimedOut ||
         jobRun?.status === JobRunStatus.DeadLettered ||
         dispatchedTooLong);

   const handleResetJob = useCallback(async () => {
      if (!selectedRunId || !resetReason.trim() || !resetJobRuns) return;

      setIsResetting(true);
      try {
         const result = await resetJobRuns([selectedRunId], resetReason.trim());

         if (result) {
            ui.success(
               `Job run has been reset successfully${result.message ? `: ${result.message}` : ""}`
            );
            setResetModalVisible(false);
            setResetReason("");
            fetchJobRunData();
            onJobRunReset();
         } else {
            ui.error("Failed to reset job run");
         }
      } catch (resetError) {
         console.error("Error resetting job run:", resetError);
         ui.error("An unexpected error occurred while resetting the job run");
      } finally {
         setIsResetting(false);
      }
   }, [
      selectedRunId,
      resetReason,
      resetJobRuns,
      fetchJobRunData,
      onJobRunReset,
      ui
   ]);

   const canCancelJobRun =
      cancelJobRun &&
      (jobRun?.status === JobRunStatus.Queued ||
         jobRun?.status === JobRunStatus.Dispatched ||
         jobRun?.status === JobRunStatus.Running);

   const handleCancelJobRun = useCallback(async () => {
      if (!selectedRunId || !cancelJobRun) return;

      setIsCancelling(true);
      try {
         const success = await cancelJobRun(selectedRunId);
         if (success) {
            ui.success("Run cancelled");
            // cancelJobRun already refreshes the run list, so only the drawer's
            // own detail needs a refresh here.
            fetchJobRunData();
         } else {
            ui.error("Failed to cancel run");
         }
      } catch (cancelError) {
         console.error("Error cancelling job run:", cancelError);
         ui.error("An unexpected error occurred while cancelling the run");
      } finally {
         setIsCancelling(false);
      }
   }, [selectedRunId, cancelJobRun, fetchJobRunData, ui]);

   const renderDetailsTab = () => (
      <>
         <Descriptions
            title="Timing"
            bordered
            column={1}
            size="small"
            style={{ marginBottom: 24, marginTop: 16 }}
         >
            <Descriptions.Item label="Created At">
               {jobRun?.createdAt
                  ? dayjs(jobRun.createdAt).format("YYYY-MM-DD HH:mm:ss")
                  : "-"}
            </Descriptions.Item>
            <Descriptions.Item label="Started At">
               {jobRun?.startedAt
                  ? dayjs(jobRun.startedAt).format("YYYY-MM-DD HH:mm:ss")
                  : "-"}
            </Descriptions.Item>
            <Descriptions.Item label="Completed At">
               {jobRun?.completedAt
                  ? dayjs(jobRun.completedAt).format("YYYY-MM-DD HH:mm:ss")
                  : "-"}
            </Descriptions.Item>
            <Descriptions.Item label="Duration">
               {getJobRunDuration(
                  jobRun?.startedAt ? new Date(jobRun.startedAt) : null,
                  jobRun?.completedAt ? new Date(jobRun.completedAt) : null
               )}
            </Descriptions.Item>
         </Descriptions>

         <Descriptions
            title="Execution Details"
            bordered
            column={1}
            size="small"
            style={{ marginBottom: 24 }}
         >
            <Descriptions.Item label="Triggered By">
               {jobRun?.jobTrigger?.triggeredBy
                  ? (renderTriggerActor?.(jobRun.jobTrigger.triggeredBy) ??
                    getTriggerActorLabel(jobRun.jobTrigger.triggeredBy))
                  : "-"}
            </Descriptions.Item>
            <Descriptions.Item label="Trigger Type">
               <Tag>
                  {getJobTriggerTypeName(
                     jobRun?.jobTrigger?.triggerType as JobTriggerType
                  )}
               </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="Attempt Count">
               {jobRun?.attemptCount || 1}
            </Descriptions.Item>
            <Descriptions.Item label="Execution ID">
               {jobRun?.executionId ? (
                  <Text code copyable={{ text: jobRun.executionId }}>
                     {jobRun.executionId}
                  </Text>
               ) : (
                  "-"
               )}
            </Descriptions.Item>
            <Descriptions.Item label="Worker">
               {jobRun?.worker ? (
                  <Text code copyable={{ text: jobRun.worker }}>
                     {jobRun.worker}
                  </Text>
               ) : (
                  "-"
               )}
            </Descriptions.Item>
         </Descriptions>

         {(jobRun?.resultType || jobRun?.resultData) && (
            <Descriptions
               title="Result"
               bordered
               column={1}
               size="small"
               style={{ marginBottom: 24 }}
            >
               <Descriptions.Item label="Result Type">
                  {jobRun.resultType || "-"}
               </Descriptions.Item>
               {jobRun.resultData && (
                  <Descriptions.Item label="Result Data">
                     <Paragraph
                        code
                        copyable
                        ellipsis={{ rows: 3, expandable: true }}
                        style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}
                     >
                        {jobRun.resultData}
                     </Paragraph>
                  </Descriptions.Item>
               )}
            </Descriptions>
         )}
      </>
   );

   const renderParametersTab = () => {
      const parametersToDisplay = jobRun?.parameters || jobRun?.job?.parameters;

      return parametersToDisplay ? (
         <JobParameterDisplay
            jobType={jobRun?.job?.type}
            configuredParameters={parametersToDisplay}
            fetchJobParametersByType={fetchJobParametersByType}
         />
      ) : (
         <div style={{ textAlign: "center", padding: "50px 0" }}>
            <Text type="secondary">
               No parameters provided or defined for this job run.
            </Text>
         </div>
      );
   };

   const tabItems: TabsProps["items"] = [
      {
         key: "details",
         label: (
            <Space size="small">
               <ProfileOutlined />
               Details
            </Space>
         ),
         children: (
            <div style={scrollableTabPaneStyle}>{renderDetailsTab()}</div>
         )
      },
      {
         key: "parameters",
         label: (
            <Space size="small">
               <SettingOutlined />
               Parameters
            </Space>
         ),
         children: (
            <div style={scrollableTabPaneStyle}>{renderParametersTab()}</div>
         )
      },
      {
         key: "logs",
         label: (
            <Space size="small">
               <OrderedListOutlined />
               Logs
            </Space>
         ),
         children: (
            <div style={logsTabPaneStyle}>
               <JobRunLogsList
                  logs={logs}
                  loading={logsLoading}
                  height={resolvedTabPaneHeight}
               />
            </div>
         )
      }
   ];

   return (
      <Drawer
         title={
            <Space>
               Job Run Details
               <Button
                  icon={<ReloadOutlined />}
                  size="small"
                  onClick={handleRefresh}
                  loading={loading || logsLoading}
               >
                  Refresh
               </Button>
            </Space>
         }
         placement="right"
         size="large"
         open={open}
         onClose={onClose}
         destroyOnHidden
         styles={{
            body: {
               display: "flex",
               flexDirection: "column",
               height: "100%",
               overflow: "hidden"
            }
         }}
      >
         {loading && !jobRun ? (
            <div style={{ textAlign: "center", padding: "50px 0" }}>
               <LoadingSpinner />
               <div style={{ marginTop: 16 }}>Loading job run details...</div>
            </div>
         ) : error ? (
            <Alert
               title="Error"
               description={error}
               type="error"
               showIcon
               action={
                  <Button size="small" danger onClick={handleRefresh}>
                     Retry Load
                  </Button>
               }
            />
         ) : jobRun ? (
            <Flex
               vertical
               style={{
                  flex: 1,
                  minHeight: 0
               }}
            >
               <Card style={{ marginBottom: 24 }}>
                  <Space orientation="vertical" style={{ width: "100%" }}>
                     <Space
                        style={{
                           display: "flex",
                           justifyContent: "space-between"
                        }}
                     >
                        <Typography.Title level={4} style={{ margin: 0 }}>
                           {jobRun.job?.name || "Unknown Job"}
                        </Typography.Title>
                        <Tag color={statusInfo.color}>{statusInfo.name}</Tag>
                     </Space>
                     <JobRunProgress
                        progress={jobRun.progress}
                        status={jobRun.status}
                     />
                     <Typography.Text type="secondary">
                        ID: {jobRun.id}
                     </Typography.Text>
                  </Space>
               </Card>

               <div
                  ref={tabsContainerRef}
                  style={{ display: "flex", flex: 1, minHeight: 0 }}
               >
                  <Tabs
                     activeKey={activeTab}
                     onChange={setActiveTab}
                     items={tabItems}
                     style={{ flex: 1, minHeight: 0 }}
                     styles={{
                        root: {
                           display: "flex",
                           flexDirection: "column",
                           flex: 1,
                           minHeight: 0
                        },
                        header: {
                           flexShrink: 0
                        }
                     }}
                  />
               </div>

               {(canResetJobRun || canCancelJobRun) && (
                  <div
                     style={{
                        marginTop: 24,
                        textAlign: "right",
                        display: "flex",
                        justifyContent: "flex-end",
                        gap: 8
                     }}
                  >
                     {canCancelJobRun && (
                        <PermissionButton
                           allowedPermissionClaims={[
                              PERMISSION_CLAIMS.JOBS_UPDATE
                           ]}
                           danger
                           loading={isCancelling}
                           onClick={() => void handleCancelJobRun()}
                        >
                           Cancel Run
                        </PermissionButton>
                     )}
                     {canResetJobRun && (
                        <PermissionButton
                           allowedPermissionClaims={[
                              PERMISSION_CLAIMS.JOBS_UPDATE
                           ]}
                           type="primary"
                           danger
                           onClick={() => {
                              setResetReason(
                                 `Reset of failed job run ${selectedRunId}`
                              );
                              setResetModalVisible(true);
                           }}
                        >
                           Reset Job Run
                        </PermissionButton>
                     )}
                  </div>
               )}

               <Modal
                  title={
                     <Space>
                        <ExclamationCircleOutlined
                           style={{ color: "orange" }}
                        />
                        Confirm Reset Job Run
                     </Space>
                  }
                  open={resetModalVisible}
                  onOk={handleResetJob}
                  onCancel={() => setResetModalVisible(false)}
                  confirmLoading={isResetting}
                  okText="Reset"
                  cancelText="Cancel"
               >
                  <Paragraph>
                     Are you sure you want to reset job run{" "}
                     <Text strong code>
                        {selectedRunId}
                     </Text>
                     ?
                  </Paragraph>
                  <Paragraph>Please provide a reason for the reset:</Paragraph>
                  <Input.TextArea
                     rows={3}
                     value={resetReason}
                     style={{ borderRadius: 8 }}
                     onChange={(event) => setResetReason(event.target.value)}
                     placeholder="Enter reason for reset (e.g., underlying data fixed, transient issue resolved)"
                  />
               </Modal>
            </Flex>
         ) : selectedRunId ? (
            <div style={{ textAlign: "center", padding: "50px 0" }}>
               <Text type="secondary">No data found for this job run.</Text>
            </div>
         ) : (
            <Text type="secondary">Select a job run to view details.</Text>
         )}
      </Drawer>
   );
};

export default JobRunDetailsDrawer;
