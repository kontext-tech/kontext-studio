import PageContainer from "@/components/layout/SeoPageContainer";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useCanViewProjectActivity } from "@/hooks/useCanViewProjectActivity";
import { RouteNames } from "@/types";
import { AccessDeniedAlert } from "@kontext-labs/auth";
import { ProjectEventsPanel } from "@kontext-labs/event";
import { useProject } from "@kontext-labs/project";
import { useUiFeedback } from "@kontext-labs/ui";

const ProjectEventsPage = () => {
   const { currentProject } = useProject();
   const apiErrorHandler = useApiErrorHandler();
   const ui = useUiFeedback();
   const canViewActivity = useCanViewProjectActivity();

   if (!currentProject) {
      return null;
   }

   if (!canViewActivity) {
      return (
         <AccessDeniedAlert
            title="Access Denied"
            description="You don't have permission to view the project activity log."
            status="403"
         />
      );
   }

   return (
      <PageContainer
         title="Activity Log"
         description={`Review the activity log for ${currentProject.projectName}.`}
         routeName={RouteNames.PROJECT_EVENTS}
         project={currentProject}
         type="project"
         showPageTitle={true}
      >
         {currentProject.id ? (
            <ProjectEventsPanel
               projectId={currentProject.id}
               errorHandler={apiErrorHandler}
               onMessage={(type, content) => ui[type](content)}
            />
         ) : null}
      </PageContainer>
   );
};

export default ProjectEventsPage;
