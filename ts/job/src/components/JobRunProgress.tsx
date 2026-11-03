import { JobRunStatus } from "@kontext-labs/schema";
import { Progress } from "antd";
import React from "react";

interface JobRunProgressProps {
   progress: number | null | undefined;
   status?: JobRunStatus;
   size?: "default" | "small";
   className?: string;
}

const JobRunProgress: React.FC<JobRunProgressProps> = ({
   progress,
   status,
   size = "small",
   className
}) => {
   if (progress == null) {
      return null;
   }

   let progressStatus: "active" | "success" | "exception" | undefined;

   if (
      status === JobRunStatus.Failed ||
      status === JobRunStatus.TimedOut ||
      status === JobRunStatus.DeadLettered
   ) {
      progressStatus = "exception";
   } else if (status === JobRunStatus.Succeeded) {
      progressStatus = "success";
   } else if (
      status === JobRunStatus.Running ||
      status === JobRunStatus.Dispatched ||
      status === JobRunStatus.Queued
   ) {
      progressStatus = "active";
   }

   return (
      <Progress
         percent={progress}
         size={size}
         status={progressStatus}
         className={className}
      />
   );
};

export default JobRunProgress;
