import PageContainer from "@/components/layout/SeoPageContainer";
import { useProjectTriggerActorRenderer } from "@/features/projects/hooks/useProjectTriggerActorRenderer";
import { useApiErrorHandler } from "@/hooks/useApiErrorHandler";
import { RouteNames } from "@/types";
import { JobRunsPanel } from "@kontext-labs/job";
import { useProject } from "@kontext-labs/project";
import { useUiFeedback } from "@kontext-labs/ui";
import { useSearchParams } from "react-router-dom";

const ProjectJobsPage = () => {
   const { currentProject } = useProject();
   const [searchParams, setSearchParams] = useSearchParams();
   const apiErrorHandler = useApiErrorHandler();
   const ui = useUiFeedback();
   const renderTriggerActor = useProjectTriggerActorRenderer();

   if (!currentProject) {
      return null;
   }

   return (
      <PageContainer
         title="Jobs"
         description={`Monitor background jobs for ${currentProject.projectName}.`}
         routeName={RouteNames.PROJECT_JOBS}
         project={currentProject}
         type="project"
         showPageTitle={true}
      >
         {currentProject.id ? (
            <JobRunsPanel
               projectId={currentProject.id}
               selectedRunId={searchParams.get("runId")}
               onSelectedRunIdChange={(runId) => {
                  const nextParams = new URLSearchParams(searchParams);
                  if (runId) {
                     nextParams.set("runId", runId);
                  } else {
                     nextParams.delete("runId");
                  }
                  setSearchParams(nextParams, { replace: true });
               }}
               errorHandler={apiErrorHandler}
               ui={ui}
               renderTriggerActor={renderTriggerActor}
            />
         ) : null}
      </PageContainer>
   );
};

export default ProjectJobsPage;
