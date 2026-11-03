import type { ApiErrorResult } from "@kontext-labs/common";
import { PlusOutlined } from "@kontext-labs/icons";
import { useService } from "@kontext-labs/app-runtime/hooks";
import type {
   AccessLevel,
   CreateProjectRequest,
   ProjectModel
} from "@kontext-labs/schema";
import {
   Button,
   Form,
   Input,
   Modal,
   Select,
   Space,
   theme,
   Typography
} from "antd";
import React, { useRef, useState } from "react";
import { ProjectService } from "../ProjectService";

const { TextArea } = Input;
const { Text } = Typography;

export interface ProjectCreateModalProps {
   open: boolean;
   onCancel: () => void;
   onSuccess: (project?: ProjectModel) => void;
   errorHandler?: (error: ApiErrorResult) => Promise<void>;
   notifySuccess?: (content: string) => void;
   notifyError?: (content: string) => void;
   defaultAccessLevel?: AccessLevel;
   showAccessLevel?: boolean;
}

export const ProjectCreateModal: React.FC<ProjectCreateModalProps> = ({
   open,
   onCancel,
   onSuccess,
   errorHandler,
   notifySuccess,
   notifyError,
   defaultAccessLevel = "Private",
   showAccessLevel = true
}) => {
   const [form] = Form.useForm();
   const [loading, setLoading] = useState(false);
   const { token } = theme.useToken();

   const projectService = useRef(
      useService(ProjectService, errorHandler)
   ).current;

   const handleSubmit = async () => {
      try {
         const values = await form.validateFields();
         setLoading(true);

         const projectData: CreateProjectRequest = {
            projectName: values.projectName.trim(),
            projectCode: values.projectCode.trim(),
            projectDescription: values.projectDescription?.trim() || null,
            accessLevel: values.accessLevel || defaultAccessLevel
         };

         const result = await projectService.createProject(projectData);

         if (result.succeed) {
            notifySuccess?.("Project created successfully");
            form.resetFields();
            onSuccess(result.data);
         } else if (result.error) {
            notifyError?.(
               result.error.messages?.[0] ?? "Failed to create project"
            );
         }
      } catch (error) {
         console.error("Form validation error:", error);
      } finally {
         setLoading(false);
      }
   };

   const handleCancel = () => {
      form.resetFields();
      onCancel();
   };

   const handleAfterOpenChange = (nextOpen: boolean) => {
      if (!nextOpen) return;

      form.setFieldValue("accessLevel", defaultAccessLevel);
   };

   const handleProjectNameChange = (
      event: React.ChangeEvent<HTMLInputElement>
   ) => {
      const name = event.target.value;
      const code = name
         .toLowerCase()
         .replace(/[^a-z0-9\s-]/g, "")
         .replace(/\s+/g, "-")
         .replace(/-+/g, "-")
         .replace(/^-|-$/g, "")
         .slice(0, 64);

      form.setFieldValue("projectCode", code);
   };

   return (
      <Modal
         title={
            <Space>
               <PlusOutlined style={{ color: token.colorPrimary }} />
               <span>Create New Project</span>
            </Space>
         }
         open={open}
         onCancel={handleCancel}
         afterOpenChange={handleAfterOpenChange}
         footer={[
            <Button key="cancel" onClick={handleCancel}>
               Cancel
            </Button>,
            <Button
               key="submit"
               type="primary"
               loading={loading}
               onClick={handleSubmit}
            >
               Create Project
            </Button>
         ]}
         destroyOnHidden
         width={600}
      >
         <div style={{ marginTop: token.marginMD }}>
            <Form
               form={form}
               layout="vertical"
               requiredMark={false}
               autoComplete="off"
               initialValues={{
                  accessLevel: defaultAccessLevel
               }}
            >
               <Form.Item
                  name="projectName"
                  label="Project Name"
                  rules={[
                     {
                        required: true,
                        message: "Please enter project name"
                     },
                     {
                        max: 1024,
                        message: "Project name cannot exceed 1024 characters"
                     }
                  ]}
               >
                  <Input
                     placeholder="Enter project name"
                     onChange={handleProjectNameChange}
                     maxLength={1024}
                     showCount
                  />
               </Form.Item>

               <Form.Item
                  name="projectCode"
                  label="Project Code"
                  extra={
                     <Text type="secondary" style={{ fontSize: "12px" }}>
                        Used in URLs and must be unique. Only letters, numbers,
                        and hyphens allowed.
                     </Text>
                  }
                  rules={[
                     {
                        required: true,
                        message: "Please enter project code"
                     },
                     {
                        max: 64,
                        message: "Project code cannot exceed 64 characters"
                     },
                     {
                        pattern: /^[a-zA-Z0-9-]+$/,
                        message:
                           "Project code can only contain letters, numbers, and hyphens"
                     }
                  ]}
               >
                  <Input placeholder="project-code" maxLength={64} showCount />
               </Form.Item>

               {showAccessLevel && (
                  <Form.Item
                     name="accessLevel"
                     label="Access Level"
                     rules={[
                        {
                           required: true,
                           message: "Please select access level"
                        }
                     ]}
                  >
                     <Select
                        placeholder="Select access level"
                        options={[
                           {
                              value: "Private",
                              label: "Private",
                              description: "Only project members can access"
                           },
                           {
                              value: "Public",
                              label: "Public",
                              description: "Anyone can view project content"
                           }
                        ]}
                     />
                  </Form.Item>
               )}

               <Form.Item
                  name="projectDescription"
                  label="Description (Optional)"
                  rules={[
                     {
                        max: 2048,
                        message: "Description cannot exceed 2048 characters"
                     }
                  ]}
               >
                  <TextArea
                     placeholder="Enter project description"
                     rows={4}
                     maxLength={2048}
                     showCount
                  />
               </Form.Item>
            </Form>
         </div>
      </Modal>
   );
};
