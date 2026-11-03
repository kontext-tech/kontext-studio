import { Progress, Tooltip, theme } from "antd";
import React from "react";

interface JobRunStatsProps {
   totalRuns: number;
   successfulRuns: number;
   failedRuns: number;
   inProgressRuns: number;
}

const JobRunStats: React.FC<JobRunStatsProps> = ({
   totalRuns,
   successfulRuns,
   failedRuns,
   inProgressRuns
}) => {
   const { token } = theme.useToken();

   if (totalRuns === 0) {
      return (
         <Tooltip title="No runs yet">
            <div style={{ padding: "8px 0" }}>
               <Progress percent={0} size="small" />
            </div>
         </Tooltip>
      );
   }

   const successPercent = (successfulRuns / totalRuns) * 100;
   const inProgressPercent = (inProgressRuns / totalRuns) * 100;
   const colorStops: Record<string, string> = {};
   let currentPosition = 0;

   if (successfulRuns > 0) {
      colorStops[`${currentPosition}%`] = token.colorSuccess;
      colorStops[`${successPercent}%`] = token.colorSuccess;
      currentPosition = successPercent;
   }

   if (inProgressRuns > 0) {
      colorStops[`${currentPosition}%`] = token.colorWarning;
      colorStops[`${currentPosition + inProgressPercent}%`] =
         token.colorWarning;
      currentPosition += inProgressPercent;
   }

   if (failedRuns > 0) {
      colorStops[`${currentPosition}%`] = token.colorError;
      colorStops["100%"] = token.colorError;
   }

   return (
      <Tooltip
         title={`Success: ${successfulRuns}, Failed: ${failedRuns}, In Progress: ${inProgressRuns}, Total: ${totalRuns}`}
      >
         <div style={{ padding: "8px 0" }}>
            <Progress
               percent={100}
               showInfo={false}
               strokeColor={colorStops}
               format={() => `${successfulRuns}/${totalRuns}`}
               size="small"
            />
            <div style={{ fontSize: 12, marginTop: 4, textAlign: "center" }}>
               {successfulRuns}/{totalRuns}
            </div>
         </div>
      </Tooltip>
   );
};

export default JobRunStats;
