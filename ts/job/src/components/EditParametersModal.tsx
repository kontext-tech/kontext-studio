import { LoadingSpinner } from "@kontext-tech/ui";
import type { UiFeedback } from "@kontext-tech/ui";
import type {
   JobRunModel,
   UnifiedJobParameterModel
} from "@kontext-tech/schema";
import { Alert, Button, Form, Input, Modal, Space, Typography } from "antd";
import React, { useEffect, useState } from "react";
import type { FetchJobParametersByTypeFn } from "../jobTypes";
import JobParameterConfigurator from "./JobParameterConfigurator";

const { Text } = Typography;

export type UpdateJobRunParametersFn = (
   runId: string,
   request: { parameters: string; reason: string }
) => Promise<JobRunModel | null>;

interface EditParametersModalProps {
   open: boolean;
   jobRun: JobRunModel | null;
   fetchJobParametersByType?: FetchJobParametersByTypeFn;
   updateJobRunParameters?: UpdateJobRunParametersFn;
   ui: UiFeedback;
   onClose: () => void;
   onSuccess: () => void;
}

const EditParametersModal: React.FC<EditParametersModalProps> = ({
   open,
   jobRun,
   fetchJobParametersByType,
   updateJobRunParameters,
   ui,
   onClose,
   onSuccess
}) => {
   const [form] = Form.useForm();
   const [parameters, setParameters] = useState<string>("");
   const [isSubmitting, setIsSubmitting] = useState(false);
   const [isLoading, setIsLoading] = useState(false);
   const [error, setError] = useState<string | null>(null);
   const [parameterDefinitions, setParameterDefinitions] = useState<
      UnifiedJobParameterModel[]
   >([]);

   const handleAfterOpenChange = (nextOpen: boolean) => {
      if (!nextOpen) return;

      const parameterValue = jobRun?.parameters || "{}";

      setParameters(parameterValue);
      form.setFieldsValue({
         parameters: parameterValue,
         reason: `Updated parameters for job run ${jobRun?.id || ""}`
      });
      setError(null);
   };

   useEffect(() => {
      const loadParameterDefinitions = async () => {
         if (!open || !jobRun?.job?.type || !fetchJobParametersByType) {
            setParameterDefinitions([]);
            setIsLoading(false);
            return;
         }

         setIsLoading(true);
         setError(null);

         try {
            const definitions = await fetchJobParametersByType(jobRun.job.type);
            setParameterDefinitions(definitions);
         } catch (loadError) {
            setError("Error loading parameter definitions");
            console.error(
               "Error fetching job parameter definitions:",
               loadError
            );
            setParameterDefinitions([]);
         } finally {
            setIsLoading(false);
         }
      };

      loadParameterDefinitions();
   }, [open, jobRun?.job?.type, fetchJobParametersByType]);

   const handleSubmit = async () => {
      try {
         const values = await form.validateFields();
         setIsSubmitting(true);
         setError(null);

         const parameterJson = values.parameters;

         try {
            JSON.parse(parameterJson);
         } catch {
            setError("Invalid JSON format. Please check your parameters.");
            setIsSubmitting(false);
            return;
         }

         if (!jobRun?.id) {
            setError("Job run ID is missing");
            setIsSubmitting(false);
            return;
         }

         if (!updateJobRunParameters) {
            setError("Editing parameters is not supported for this job type");
            setIsSubmitting(false);
            return;
         }

         const result = await updateJobRunParameters(jobRun.id, {
            parameters: parameterJson,
            reason: values.reason
         });

         if (result) {
            ui.success("Job parameters updated successfully");
            onSuccess();
            onClose();
         } else {
            setError("Failed to update parameters");
         }
      } catch {
         setError("An error occurred while submitting the form");
      } finally {
         setIsSubmitting(false);
      }
   };

   return (
      <Modal
         title={`Edit Parameters - ${jobRun?.job?.name || "Unknown Job"}`}
         open={open}
         onCancel={onClose}
         afterOpenChange={handleAfterOpenChange}
         footer={[
            <Button key="cancel" onClick={onClose}>
               Cancel
            </Button>,
            <Button
               key="submit"
               type="primary"
               loading={isSubmitting}
               onClick={handleSubmit}
            >
               Update Parameters
            </Button>
         ]}
         width={700}
         destroyOnHidden
      >
         {error && (
            <Alert
               title="Error"
               description={error}
               type="error"
               showIcon
               style={{ marginBottom: 16 }}
            />
         )}

         <Form form={form} layout="vertical">
            <Form.Item
               name="parameters"
               label="Parameters"
               rules={[
                  { required: true, message: "Please enter parameters" },
                  {
                     validator: (_, value) => {
                        try {
                           if (value) JSON.parse(value);
                           return Promise.resolve();
                        } catch {
                           return Promise.reject("Invalid JSON format");
                        }
                     }
                  }
               ]}
            >
               {isLoading ? (
                  <LoadingSpinner />
               ) : (
                  <JobParameterConfigurator
                     parameters={parameterDefinitions}
                     value={parameters}
                     onChange={(value) => {
                        setParameters(value);
                        form.setFieldsValue({ parameters: value });
                     }}
                     disabled={isSubmitting}
                  />
               )}
            </Form.Item>

            <Space
               orientation="vertical"
               style={{ width: "100%", marginBottom: 16 }}
            >
               <Text type="secondary">
                  Parameters must be in valid JSON format. Only queued and
                  failed jobs can have their parameters updated.
               </Text>
            </Space>

            <Form.Item
               name="reason"
               label="Reason for Update"
               rules={[
                  {
                     required: true,
                     message: "Please provide a reason for this update"
                  },
                  { min: 3, message: "Reason must be at least 3 characters" }
               ]}
            >
               <Input placeholder="Why are you updating these parameters?" />
            </Form.Item>
         </Form>
      </Modal>
   );
};

export default EditParametersModal;
