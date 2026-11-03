import { logger } from "@kontext-labs/common";
import {
   CheckCircleOutlined,
   ClockCircleOutlined,
   SettingOutlined,
   ToolOutlined
} from "@kontext-labs/icons";
import type { UnifiedJobTypeModel } from "@kontext-labs/schema";
import { Button, Form, Grid, Modal, Space, Steps } from "antd";
import React, { useEffect, useState } from "react";
import type { JobFormData } from "../../jobTypes";
import BasicInfoStep from "./BasicInfoStep";
import ParametersStep from "./ParametersStep";
import ReviewStep from "./ReviewStep";
import ScheduleStep from "./ScheduleStep";
import type { JobFormModalProps, StepConfig } from "./modalTypes";

const JobFormModal: React.FC<JobFormModalProps> = ({
   open,
   editingJob,
   jobTypes,
   jobTypesLoading,
   loading,
   ui,
   onOk,
   onCancel
}) => {
   const [form] = Form.useForm<JobFormData>();
   const { useBreakpoint } = Grid;
   const screens = useBreakpoint();
   const [currentStep, setCurrentStep] = useState(0);
   const [selectedJobType, setSelectedJobType] =
      useState<UnifiedJobTypeModel | null>(null);
   const [parametersValue, setParametersValue] = useState<string>("");
   const [scheduleMode, setScheduleMode] = useState<"manual" | "scheduled">(
      "manual"
   );

   const getStepsConfig = React.useCallback((): StepConfig[] => {
      const baseSteps: StepConfig[] = [
         {
            title: "Basic Info",
            icon: <SettingOutlined />,
            description: "Job name, type, and project",
            key: "basic"
         },
         {
            title: "Schedule",
            icon: <ClockCircleOutlined />,
            description: "Set up job execution schedule",
            key: "schedule"
         },
         {
            title: "Review",
            icon: <CheckCircleOutlined />,
            description: "Review and confirm",
            key: "review"
         }
      ];

      const hasParameters =
         selectedJobType?.parameters && selectedJobType.parameters.length > 0;

      if (hasParameters) {
         baseSteps.splice(1, 0, {
            title: "Parameters",
            icon: <ToolOutlined />,
            description: "Configure job parameters",
            key: "parameters"
         });
      }
      return baseSteps;
   }, [selectedJobType]);

   const stepsConfig = getStepsConfig();

   useEffect(() => {
      if (!open) return;

      const timeoutId = window.setTimeout(() => {
         if (editingJob) {
            const initialValues = {
               name: editingJob.name || "",
               description: editingJob.description || "",
               type: editingJob.type || "",
               parameters: editingJob.parameters || "",
               schedule: editingJob.schedule || "",
               projectId: editingJob.projectId || "",
               isEnabled:
                  editingJob.isEnabled !== undefined
                     ? editingJob.isEnabled
                     : true
            };

            setScheduleMode(editingJob.schedule ? "scheduled" : "manual");
            form.resetFields();
            form.setFieldsValue(initialValues);
            setParametersValue(editingJob.parameters || "");

            const jobType = jobTypes.find(
               (item) => item.type === editingJob.type
            );
            setSelectedJobType(jobType || null);
            setCurrentStep(0);
            return;
         }

         form.resetFields();
         setSelectedJobType(null);
         setParametersValue("");
         setScheduleMode("manual");
         setCurrentStep(0);
         form.setFieldsValue({
            name: "",
            description: "",
            type: "",
            parameters: "",
            schedule: "",
            projectId: "",
            isEnabled: true
         });
      }, 0);

      return () => window.clearTimeout(timeoutId);
   }, [open, editingJob, jobTypes, form]);

   const handleNext = async () => {
      try {
         const currentStepConfig = stepsConfig[currentStep];

         if (currentStepConfig.key === "basic") {
            await form.validateFields(["type", "name"]);
         } else if (currentStepConfig.key === "parameters") {
            const currentParameters = form.getFieldValue("parameters");
            if (currentParameters?.trim()) {
               try {
                  JSON.parse(currentParameters);
               } catch {
                  ui.error("Invalid JSON format in parameters");
                  return;
               }
            }
         } else if (
            currentStepConfig.key === "schedule" &&
            scheduleMode === "scheduled"
         ) {
            await form.validateFields(["schedule"]);
         }

         if (currentStep < stepsConfig.length - 1) {
            setCurrentStep(currentStep + 1);
         }
      } catch (errorInfo) {
         logger.debug("Validation failed:", errorInfo);
         if (stepsConfig[currentStep].key === "basic") {
            ui.error(
               "Please fill in all required fields in the Basic Info step."
            );
         } else if (stepsConfig[currentStep].key === "schedule") {
            ui.error("Please correct the errors in the Schedule step.");
         }
      }
   };

   const handleOk = async () => {
      try {
         const values = await form.validateFields();

         let parsedParameters = undefined;
         if (values.parameters?.trim()) {
            try {
               parsedParameters = JSON.parse(values.parameters);
            } catch {
               ui.error("Invalid JSON format in parameters");
               return;
            }
         }

         const schedule = scheduleMode === "manual" ? "" : values.schedule;

         await onOk({
            ...values,
            parameters: parsedParameters
               ? JSON.stringify(parsedParameters)
               : undefined,
            schedule
         });
      } catch {
         // AntD form handles field errors.
      }
   };

   const stepProps = {
      form,
      editingJob,
      jobTypes,
      jobTypesLoading,
      selectedJobType,
      setSelectedJobType,
      parametersValue,
      setParametersValue,
      scheduleMode,
      setScheduleMode
   };

   return (
      <Modal
         title={editingJob ? "Edit Job" : "Create Job"}
         open={open}
         onCancel={() => {
            form.resetFields();
            setCurrentStep(0);
            setSelectedJobType(null);
            setParametersValue("");
            setScheduleMode("manual");
            onCancel();
         }}
         maskClosable={false}
         keyboard={false}
         width={
            screens.xs
               ? "100vw"
               : screens.sm
                 ? "90vw"
                 : screens.md
                   ? "80vw"
                   : "60vw"
         }
         style={{
            maxWidth: "1400px",
            top: screens.xs ? 0 : 20
         }}
         styles={{
            body: {
               paddingTop: 20,
               minHeight: screens.xs ? "70vh" : "60vh",
               maxHeight: screens.xs ? "80vh" : "75vh",
               overflowY: "auto"
            }
         }}
         footer={
            <Space wrap size={screens.xs ? "small" : "middle"}>
               <Button
                  onClick={() => {
                     form.resetFields();
                     setCurrentStep(0);
                     setSelectedJobType(null);
                     setParametersValue("");
                     setScheduleMode("manual");
                     onCancel();
                  }}
               >
                  Cancel
               </Button>
               {currentStep > 0 && (
                  <Button onClick={() => setCurrentStep(currentStep - 1)}>
                     Previous
                  </Button>
               )}
               {currentStep < stepsConfig.length - 1 && (
                  <Button type="primary" onClick={handleNext}>
                     Next
                  </Button>
               )}
               {currentStep === stepsConfig.length - 1 && (
                  <Button type="primary" loading={loading} onClick={handleOk}>
                     {editingJob ? "Save Changes" : "Create Job"}
                  </Button>
               )}
            </Space>
         }
      >
         <Steps
            current={currentStep}
            orientation={screens.xs ? "vertical" : "horizontal"}
            size={screens.xs ? "small" : "default"}
            responsive={false}
            items={stepsConfig.map((step) => ({
               title: step.title,
               icon: step.icon,
               content: screens.md ? step.description : undefined
            }))}
            style={{ marginBottom: 24 }}
         />
         <Form form={form} layout="vertical" name="jobForm">
            {stepsConfig.map((step, index) => {
               if (step.key === "basic") {
                  return (
                     <BasicInfoStep
                        {...stepProps}
                        isVisible={currentStep === index}
                        key={step.key}
                     />
                  );
               }
               if (step.key === "parameters") {
                  return (
                     <ParametersStep
                        {...stepProps}
                        isVisible={currentStep === index}
                        key={step.key}
                     />
                  );
               }
               if (step.key === "schedule") {
                  return (
                     <ScheduleStep
                        {...stepProps}
                        isVisible={currentStep === index}
                        key={step.key}
                     />
                  );
               }
               if (step.key === "review") {
                  return (
                     <ReviewStep
                        {...stepProps}
                        isVisible={currentStep === index}
                        key={step.key}
                     />
                  );
               }
               return null;
            })}
         </Form>
      </Modal>
   );
};

export default JobFormModal;
