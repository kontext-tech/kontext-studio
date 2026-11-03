import type { JobModel, UnifiedJobTypeModel } from "@kontext-tech/schema";
import type { UiFeedback } from "@kontext-tech/ui";
import type { FormInstance } from "antd";
import type { JobFormData } from "../../jobTypes";

export interface JobFormModalProps {
   open: boolean;
   editingJob: JobModel | null;
   jobTypes: UnifiedJobTypeModel[];
   jobTypesLoading: boolean;
   loading: boolean;
   ui: UiFeedback;
   onOk: (formData: JobFormData) => Promise<void>;
   onCancel: () => void;
}

export interface StepProps {
   form: FormInstance<JobFormData>;
   editingJob: JobModel | null;
   jobTypes?: UnifiedJobTypeModel[];
   jobTypesLoading?: boolean;
   selectedJobType: UnifiedJobTypeModel | null;
   setSelectedJobType: (jobType: UnifiedJobTypeModel | null) => void;
   parametersValue: string;
   setParametersValue: (value: string) => void;
   scheduleMode: "manual" | "scheduled";
   setScheduleMode: (mode: "manual" | "scheduled") => void;
   isVisible: boolean;
}

export interface StepConfig {
   title: string;
   icon: React.ReactNode;
   description: string;
   key: string;
}
