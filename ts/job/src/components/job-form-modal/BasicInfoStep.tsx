import { Form, Grid, Input, Select, Space, Typography } from "antd";
import React from "react";
import RuntimeBadge from "../RuntimeBadge";
import type { StepProps } from "./modalTypes";

const { TextArea } = Input;
const { Title, Text } = Typography;

const BasicInfoStep: React.FC<StepProps> = ({
   form,
   jobTypes = [],
   jobTypesLoading = false,
   setSelectedJobType,
   isVisible
}) => {
   const { useBreakpoint } = Grid;
   const screens = useBreakpoint();

   const handleJobTypeChange = (jobTypeValue: string) => {
      const jobType = jobTypes.find((item) => item.type === jobTypeValue);
      setSelectedJobType(jobType || null);

      const currentName = form.getFieldValue("name");
      if (!currentName && jobType?.name) {
         setTimeout(() => {
            const latestName = form.getFieldValue("name");
            if (!latestName && jobType?.name) {
               form.setFieldValue("name", jobType.name);
            }
         }, 0);
      }

      form.setFieldValue("parameters", "");
   };

   const jobTypeOptions = jobTypes.map((jobType) => ({
      label: jobType.name || jobType.type || "",
      value: jobType.type!,
      description: jobType.description,
      runtime: jobType.runtime,
      category: jobType.category
   }));

   return (
      <div style={{ display: isVisible ? "block" : "none" }}>
         <Title level={screens.xs ? 5 : 4}>Basic Information</Title>
         <Text type="secondary">Enter the basic details for your job</Text>
         <Form.Item
            name="type"
            label="Job Type"
            rules={[{ required: true, message: "Please select a job type" }]}
            style={{ marginTop: 24 }}
         >
            <Select
               placeholder="Select job type"
               options={jobTypeOptions}
               loading={jobTypesLoading}
               showSearch={{ optionFilterProp: "label" }}
               onChange={handleJobTypeChange}
               optionRender={(option) => (
                  <Space orientation="vertical" size="small">
                     <Text>{option.data.label}</Text>
                     {option.data.description && screens.sm && (
                        <Text
                           type="secondary"
                           style={{ fontSize: screens.xs ? "12px" : "14px" }}
                        >
                           {option.data.description}
                        </Text>
                     )}
                     {option.data.runtime && (
                        <RuntimeBadge runtime={option.data.runtime} />
                     )}
                  </Space>
               )}
            />
         </Form.Item>

         <Form.Item
            name="name"
            label="Job Name"
            rules={[
               { required: true, message: "Please enter a job name" },
               {
                  max: 100,
                  message: "Job name must be less than 100 characters"
               }
            ]}
         >
            <Input placeholder="Enter job name" />
         </Form.Item>

         <Form.Item name="description" label="Description">
            <TextArea
               placeholder="Enter job description"
               rows={screens.xs ? 2 : 3}
               maxLength={500}
               showCount
               style={{ borderRadius: 8 }}
            />
         </Form.Item>

         <Form.Item
            name="projectId"
            label="Project ID"
            help="Optional. Leave empty for system jobs."
         >
            <Input placeholder="Enter project ID" />
         </Form.Item>
      </div>
   );
};

export default BasicInfoStep;
