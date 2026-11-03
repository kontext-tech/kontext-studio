import type {
   JobModel,
   JobRunModel,
   JobRunStatus,
   UnifiedJobParameterModel
} from "@kontext-labs/schema";
import type { UiFeedback } from "@kontext-labs/ui";

export interface JobFormData {
   name: string;
   description?: string;
   type: string;
   isEnabled: boolean;
   parameters?: string;
   schedule?: string;
   projectId?: string;
}

export type FetchJobParametersByTypeFn = (
   jobType: string
) => Promise<UnifiedJobParameterModel[]>;

export interface JobActionsProps {
   job: JobModel;
   ui: UiFeedback;
   onEdit: (job: JobModel) => void;
   onDelete: (jobId: string, jobName: string) => void;
   onSchedule: (jobId: string, jobName: string) => void;
   onDisableSchedule: (job: JobModel) => void;
}

export interface JobRunActionsProps {
   jobRun: JobRunModel;
   ui: UiFeedback;
   onViewDetails: (runId: string) => void;
   onCancel?: (runId: string, jobName: string) => void;
   onEditParameters?: (runId: string) => void;
}

export interface JobRunFilters {
   status?: JobRunStatus;
   startDate?: Date;
   endDate?: Date;
   jobId?: string;
   projectId?: string;
}

export interface JobRunStatistics {
   runningJobs: JobRunModel[];
   failedJobs: JobRunModel[];
   totalCount: number;
   totalJobCount: number;
}
