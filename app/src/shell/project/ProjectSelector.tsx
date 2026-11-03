import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useRoute } from "@/hooks/useRoute";
import { usePermissionContext } from "@/context/AppPermissionContext";
import type { ProjectRole } from "@kontext-labs/auth";
import { useUser } from "@kontext-labs/identity";
import { ProjectSelectorModal, useProject } from "@kontext-labs/project";
import type { ProjectModel } from "@kontext-labs/schema";
import { useNavigate } from "react-router-dom";

interface ProjectSelectorProps {
   inSidebar?: boolean;
   collapsed?: boolean;
}

const ProjectSelector = ({
   inSidebar = false,
   collapsed = false
}: ProjectSelectorProps) => {
   const apiErrorHandler = useApiErrorHandler();
   const { currentProject, setCurrentProject } = useProject();
   const { isProjectAdmin } = usePermissionContext();
   const { getUserRolesForProject } = useUser();
   const navigate = useNavigate();
   const { getProjectChatPath, getProjectHomePath, getProjectSettingsPath } =
      useRoute();

   const handleSelectProject = (project: ProjectModel) => {
      setCurrentProject(project);
      navigate(getProjectHomePath(project));
   };

   return (
      <ProjectSelectorModal
         currentProject={currentProject}
         inSidebar={inSidebar}
         collapsed={collapsed}
         errorHandler={apiErrorHandler}
         onSelectProject={handleSelectProject}
         onOpenProject={(project) => navigate(getProjectHomePath(project))}
         onOpenChat={(project) => navigate(getProjectChatPath(project))}
         onOpenSettings={(project) => navigate(getProjectSettingsPath(project))}
         getProjectRoles={(project) =>
            getUserRolesForProject(project.id) as ProjectRole[]
         }
         canOpenSettings={(project) => isProjectAdmin(project)}
      />
   );
};

export default ProjectSelector;
