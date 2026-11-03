import type { ApiErrorResult } from "@kontext-labs/common";
import type { TriggerActorModel } from "@kontext-labs/schema";
import type { UiFeedback } from "@kontext-labs/ui";
import React, { useState, type ReactNode } from "react";
import { useDataJobRuns } from "../useDataJobRuns";
import { useDataJobTypes } from "../useDataJobTypes";
import JobRunDetailsDrawer from "./JobRunDetailsDrawer";

export interface JobRunDetailsDrawerHostProps {
   projectId: string;
   /** Run id to display; null closes the drawer. */
   runId: string | null;
   onClose: () => void;
   ui: UiFeedback;
   errorHandler?: (error: ApiErrorResult) => Promise<void>;
   renderTriggerActor?: (actor: TriggerActorModel) => ReactNode;
}

/**
 * Job run details drawer wired directly to the job data services — the same
 * drawer JobRunsPanel embeds, minus the runs table. Hosts render it (e.g.
 * notebook pages) to inspect a single run without navigating away.
 */
const JobRunDetailsDrawerHost: React.FC<JobRunDetailsDrawerHostProps> = ({
   runId,
   ...rest
}) => {
   // Mount the service-wired drawer lazily (on first open) so idle hosts do
   // not issue job-type/run list queries; once opened it stays mounted so the
   // drawer keeps its open/close transitions. Render-phase state adjustment
   // (see https://react.dev/learn/you-might-not-need-an-effect).
   const [hasOpened, setHasOpened] = useState(false);
   if (runId && !hasOpened) {
      setHasOpened(true);
   }

   if (!hasOpened) {
      return null;
   }

   return <JobRunDetailsDrawerContent runId={runId} {...rest} />;
};

const JobRunDetailsDrawerContent: React.FC<JobRunDetailsDrawerHostProps> = ({
   projectId,
   runId,
   onClose,
   ui,
   errorHandler,
   renderTriggerActor
}) => {
   const { fetchJobParametersByType } = useDataJobTypes(
      projectId,
      errorHandler
   );
   const { getJobRun, getJobRunLogs, resetJobRuns, cancelJobRun, loadJobRuns } =
      useDataJobRuns(projectId, errorHandler);

   return (
      <JobRunDetailsDrawer
         open={!!runId}
         selectedRunId={runId}
         fetchJobParametersByType={fetchJobParametersByType}
         getJobRun={getJobRun}
         getJobRunLogs={getJobRunLogs}
         resetJobRuns={resetJobRuns}
         cancelJobRun={cancelJobRun}
         ui={ui}
         onClose={onClose}
         onJobRunReset={() => void loadJobRuns()}
         renderTriggerActor={renderTriggerActor}
      />
   );
};

export default JobRunDetailsDrawerHost;
