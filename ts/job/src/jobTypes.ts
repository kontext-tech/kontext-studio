import type {
   JobRunModel,
   JobRunStatus,
   UnifiedJobParameterModel
} from "@kontext-tech/schema";
import type { UiFeedback } from "@kontext-tech/ui";

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
