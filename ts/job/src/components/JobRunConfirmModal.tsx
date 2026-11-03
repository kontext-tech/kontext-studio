import { PlayCircleOutlined } from "@kontext-labs/icons";
import type { JobModel, UnifiedJobTypeModel } from "@kontext-labs/schema";
import { Alert, Grid, Modal, Space, Typography } from "antd";
import React, { useState } from "react";
import JobParameterConfigurator from "./JobParameterConfigurator";

const { Text } = Typography;

interface JobRunConfirmModalProps {
   open: boolean;
   job: JobModel | null;
   jobTypes: UnifiedJobTypeModel[];
   loading?: boolean;
   onOk: (parameters?: string) => void;
   onCancel: () => void;
}

const JobRunConfirmModal: React.FC<JobRunConfirmModalProps> = ({
   open,
   job,
   jobTypes,
   loading = false,
   onOk,
   onCancel
}) => {
   const [parameters, setParameters] = useState<string>("");
   const { useBreakpoint } = Grid;
   const screens = useBreakpoint();

   const jobType = jobTypes.find((jobTypeDef) => jobTypeDef.type === job?.type);
   const handleAfterOpenChange = (nextOpen: boolean) => {
      if (!nextOpen) return;

      setParameters(job?.parameters || "");
   };

   const hasParameters = !!jobType?.parameters && jobType.parameters.length > 0;

   return (
      <Modal
         title={
            <Space>
               <PlayCircleOutlined />
               <span>Run Job: {job?.name}</span>
            </Space>
         }
         open={open}
         afterOpenChange={handleAfterOpenChange}
         onOk={() => onOk(parameters || undefined)}
         onCancel={() => {
            setParameters("");
            onCancel();
         }}
         confirmLoading={loading}
         okText="Run Job"
         cancelText="Cancel"
         width={
            screens.xs
               ? "100vw"
               : screens.sm
                 ? "90vw"
                 : hasParameters
                   ? "800px"
                   : "500px"
         }
         style={{
            maxWidth: hasParameters ? "800px" : "500px",
            top: screens.xs ? 0 : 20
         }}
         destroyOnHidden
      >
         <Space orientation="vertical" size="large" style={{ width: "100%" }}>
            <Alert
               title="Confirm Job Execution"
               description={`You are about to run the job "${job?.name}" immediately. ${
                  hasParameters
                     ? "You can review and modify the parameters below before running."
                     : "This job does not require any parameters."
               }`}
               type="info"
               showIcon
            />

            {job?.description && (
               <div>
                  <Text strong>Description:</Text>
                  <div style={{ marginTop: 4 }}>
                     <Text type="secondary">{job.description}</Text>
                  </div>
               </div>
            )}

            {hasParameters && (
               <div>
                  <Text strong>Job Parameters:</Text>
                  <div style={{ marginTop: 8 }}>
                     <JobParameterConfigurator
                        parameters={jobType!.parameters!}
                        value={parameters}
                        onChange={setParameters}
                        disabled={loading}
                     />
                  </div>
               </div>
            )}

            {!hasParameters && (
               <Alert
                  title="No Parameters Required"
                  description="This job will run with its default configuration."
                  type="success"
                  showIcon
               />
            )}
         </Space>
      </Modal>
   );
};

export default JobRunConfirmModal;
