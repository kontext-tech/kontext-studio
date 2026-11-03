import type { ProjectRole } from "@kontext-tech/auth";
import type { ApiErrorResult } from "@kontext-tech/common";
import type { ProjectModel } from "@kontext-tech/schema";
import { Modal } from "antd";
import { useState } from "react";
import ProjectSelectorPanel, {
   ProjectSelectorTrigger
} from "./ProjectSelectorPanel";

export interface ProjectSelectorModalProps {
   currentProject?: ProjectModel | null;
   inSidebar?: boolean;
   collapsed?: boolean;
   errorHandler?: (error: ApiErrorResult) => Promise<void>;
   onSelectProject: (project: ProjectModel) => void;
   onOpenProject?: (project: ProjectModel) => void;
   onOpenChat?: (project: ProjectModel) => void;
   onOpenSettings?: (project: ProjectModel) => void;
   getProjectRoles?: (project: ProjectModel) => ProjectRole[];
   canOpenSettings?: (project: ProjectModel) => boolean;
}

export const ProjectSelectorModal = ({
   currentProject,
   inSidebar = false,
   collapsed = false,
   errorHandler,
   onSelectProject,
   onOpenProject,
   onOpenChat,
   onOpenSettings,
   getProjectRoles,
   canOpenSettings
}: ProjectSelectorModalProps) => {
   const [isOpen, setIsOpen] = useState(false);

   const closeModal = () => {
      setIsOpen(false);
   };

   const handleSelectProject = (project: ProjectModel) => {
      closeModal();
      onSelectProject(project);
   };

   return (
      <>
         <ProjectSelectorTrigger
            currentProject={currentProject}
            onClick={() => setIsOpen(true)}
            inSidebar={inSidebar}
            collapsed={collapsed}
         />
         <Modal
            title="Select Project"
            open={isOpen}
            onCancel={closeModal}
            footer={null}
            width={860}
            styles={{
               body: { maxHeight: "64vh", overflow: "auto", padding: "20px" }
            }}
         >
            <ProjectSelectorPanel
               visible={isOpen}
               currentProject={currentProject}
               errorHandler={errorHandler}
               onSelectProject={handleSelectProject}
               onOpenProject={onOpenProject}
               onOpenChat={onOpenChat}
               onOpenSettings={onOpenSettings}
               getProjectRoles={getProjectRoles}
               canOpenSettings={canOpenSettings}
               loadingFallbackStyle={
                  inSidebar ? { padding: "16px 24px" } : { marginLeft: "16px" }
               }
            />
         </Modal>
      </>
   );
};
