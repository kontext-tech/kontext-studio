import { JobRunStatus, JobTriggerType } from "@kontext-labs/schema";
import type { TriggerActorModel } from "@kontext-labs/schema";
import dayjs from "dayjs";

const JOB_RUN_STATUS_MAP: Record<
   JobRunStatus,
   { name: string; color: string }
> = {
   [JobRunStatus.Queued]: { name: "Queued", color: "blue" },
   [JobRunStatus.Dispatched]: { name: "Dispatched", color: "geekblue" },
   [JobRunStatus.Running]: { name: "Running", color: "processing" },
   [JobRunStatus.Succeeded]: { name: "Succeeded", color: "success" },
   [JobRunStatus.Failed]: { name: "Failed", color: "error" },
   [JobRunStatus.Canceled]: { name: "Canceled", color: "warning" },
   [JobRunStatus.TimedOut]: { name: "Timed Out", color: "error" },
   [JobRunStatus.DeadLettered]: { name: "Dead Lettered", color: "error" }
};

export const getJobRunStatusInfo = (status?: JobRunStatus) => {
   if (status === undefined || !JOB_RUN_STATUS_MAP[status]) {
      return { name: "Unknown", color: "default" };
   }
   return JOB_RUN_STATUS_MAP[status];
};

const JOB_TRIGGER_TYPE_MAP: Record<JobTriggerType, string> = {
   [JobTriggerType.Manual]: "Manual",
   [JobTriggerType.Scheduled]: "Scheduled",
   [JobTriggerType.Event]: "Event",
   [JobTriggerType.Retry]: "Retry",
   [JobTriggerType.Dependency]: "Dependency",
   [JobTriggerType.Interactive]: "Interactive"
};

export const getJobTriggerTypeName = (triggerType?: JobTriggerType) => {
   if (triggerType === undefined || !JOB_TRIGGER_TYPE_MAP[triggerType]) {
      return "Unknown";
   }
   return JOB_TRIGGER_TYPE_MAP[triggerType];
};

export const getJobRunDuration = (
   startTime?: Date | null,
   endTime?: Date | null
): string => {
   if (!startTime) return "-";
   const start = dayjs(startTime);
   const end = endTime ? dayjs(endTime) : dayjs();
   const durationMs = end.diff(start, "millisecond");
   const durationSec = Math.floor(durationMs / 1000);

   if (durationSec < 60) {
      const ms = durationMs % 1000;
      return ms > 0
         ? `${durationSec}.${ms.toString().padStart(3, "0")}s`
         : `${durationSec}s`;
   }
   if (durationSec < 3600) {
      return `${Math.floor(durationSec / 60)}m ${durationSec % 60}s`;
   }
   return `${Math.floor(durationSec / 3600)}h ${Math.floor((durationSec % 3600) / 60)}m`;
};

/**
 * Human-readable label for a structured trigger actor.
 *
 * The label is intentionally generic; callers that can resolve a route should
 * render a link instead and use this only as the fallback text.
 */
export const getTriggerActorLabel = (
   actor?: TriggerActorModel | null
): string | undefined => {
   if (!actor) {
      return undefined;
   }

   const shortId = actor.id ? actor.id.slice(0, 8) : undefined;

   switch (actor.type) {
      case "User":
         return shortId ? `User ${shortId}` : "User";
      case "Notebook":
         return "Notebook";
      case "ChatSession":
         return "Chat session";
      case "File":
         return "File";
      case "Agent":
         return actor.id ?? "Agent";
      case "Scheduler":
         return shortId ? `Scheduler ${shortId}` : "Scheduler";
      case "Event":
         return shortId ? `Event ${shortId}` : "Event";
      case "System":
         return actor.id ?? "System";
      default:
         return actor.type;
   }
};
