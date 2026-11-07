import type { ApiErrorResult } from "@kontext-tech/common";
import type { UiFeedback } from "@kontext-tech/ui";
import { getFullUrl } from "@kontext-tech/common/utils";
import { QuestionCircleOutlined } from "@kontext-tech/icons";
import { useService } from "@kontext-tech/app-runtime/hooks";
import type { ProjectModel, UpdateProjectRequest } from "@kontext-tech/schema";
import { Button, Card, Flex, Form, Input, Tooltip } from "antd";
import { useState } from "react";
import { ProjectService } from "../ProjectService";

const { TextArea } = Input;

export interface ProjectDetailsFormProps {
   project: ProjectModel;
   onProjectUpdated: (updatedProject: ProjectModel) => void;
   errorHandler?: (error: ApiErrorResult) => Promise<void>;
   ui?: UiFeedback;
   modifiedByUserId?: string;
   helpUrl?: string;
}

export const ProjectDetailsForm = ({
   project,
   onProjectUpdated,
   errorHandler,
   ui,
   modifiedByUserId,
   helpUrl = getFullUrl("docs/project-settings")
}: ProjectDetailsFormProps) => {
   const [form] = Form.useForm();
   const [isSaving, setIsSaving] = useState(false);

   const projectService = useService(ProjectService, errorHandler);

   const handleSubmit = async (values: {
      projectName: string;
      projectDescription: string;
   }) => {
      if (!project?.id) {
         ui?.error("Project not found");
         return;
      }

      setIsSaving(true);

      const updateModel: UpdateProjectRequest = {
         id: project.id,
         projectName: values.projectName,
         projectDescription: values.projectDescription,
         modifyByUserId: modifiedByUserId
      };

      const response = await projectService.updateProject(
         project.id,
         updateModel
      );

      setIsSaving(false);

      if (response.succeed) {
         ui?.success("Project settings updated successfully");
         onProjectUpdated({
            ...project,
            projectName: updateModel.projectName,
            projectDescription: updateModel.projectDescription
         } as ProjectModel);
      } else {
         ui?.error(response.error?.title || "Failed to update project");
      }
   };

   return (
      <Card
         title="Edit Project Details"
         extra={
            <Tooltip title="Read guide: Change project basic settings">
               <a
                  href={helpUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label="Project settings guide"
               >
                  <QuestionCircleOutlined />
               </a>
            </Tooltip>
         }
      >
         <Form
            form={form}
            layout="vertical"
            onFinish={handleSubmit}
            initialValues={{
               projectName: project.projectName,
               projectDescription: project.projectDescription,
               accessLevel: project.accessLevel
            }}
         >
            <Form.Item
               label="Project Name"
               name="projectName"
               rules={[
                  {
                     required: true,
                     message: "Please enter the project name"
                  },
                  {
                     max: 100,
                     message: "Project name cannot exceed 100 characters"
                  }
               ]}
            >
               <Input />
            </Form.Item>

            <Form.Item
               label="Project Description"
               name="projectDescription"
               rules={[
                  {
                     max: 500,
                     message: "Description cannot exceed 500 characters"
                  }
               ]}
            >
               <TextArea
                  rows={4}
                  placeholder="Enter a description for your project"
                  style={{ borderRadius: "8px" }}
               />
            </Form.Item>

            <Flex justify="end">
               <Button type="primary" htmlType="submit" loading={isSaving}>
                  Save Changes
               </Button>
            </Flex>
         </Form>
      </Card>
   );
};
