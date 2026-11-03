import PageContainer from "@/components/layout/SeoPageContainer";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { useCanViewProjectActivity } from "@/hooks/useCanViewProjectActivity";
import { RouteNames } from "@/types";
import { AccessDeniedAlert } from "@kontext-labs/auth";
import { useProject } from "@kontext-labs/project";
import { ProjectQuerySessionsPanel } from "@kontext-labs/query";
import { useUiFeedback } from "@kontext-labs/ui";

const ProjectQuerySessionsPage = () => {
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
            description="You don't have permission to view project query session history."
            status="403"
         />
      );
   }

   return (
      <PageContainer
         title="Query Session History"
         description={`Review query session history for ${currentProject.projectName}.`}
         routeName={RouteNames.PROJECT_QUERY_SESSIONS}
         project={currentProject}
         type="project"
         showPageTitle={true}
      >
         {currentProject.id ? (
            <ProjectQuerySessionsPanel
               projectId={currentProject.id}
               errorHandler={apiErrorHandler}
               onMessage={(type, content) => ui[type](content)}
            />
         ) : null}
      </PageContainer>
   );
};

export default ProjectQuerySessionsPage;
