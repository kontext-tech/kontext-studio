import { PermissionButton } from "@kontext-labs/auth";
import { PERMISSION_CLAIMS } from "@kontext-labs/auth";
import { EditOutlined, EyeOutlined, StopOutlined } from "@kontext-labs/icons";
import { JobRunStatus } from "@kontext-labs/schema";
import { Space } from "antd";
import React from "react";
import type { JobRunActionsProps } from "../jobTypes";

const JobRunActions: React.FC<JobRunActionsProps> = ({
   jobRun,
   ui,
   onViewDetails,
   onCancel,
   onEditParameters
}) => {
   const handleCancel = () => {
      if (onCancel) {
         onCancel(jobRun.id!, jobRun.job?.name || "Unknown Job");
      } else {
         ui.info("Job cancellation functionality coming soon");
      }
   };

   const handleEditParameters = () => {
      if (onEditParameters) {
         onEditParameters(jobRun.id!);
      } else {
         ui.info("Parameter editing functionality coming soon");
      }
   };

   return (
      <Space size="small">
         <PermissionButton
            allowedPermissionClaims={[PERMISSION_CLAIMS.JOBS_READ]}
            type="text"
            icon={<EyeOutlined />}
            size="small"
            onClick={() => onViewDetails(jobRun.id || "")}
            tooltipWhenEnabled="View Details"
            useNativeTooltip={true}
         />
         {(jobRun.status === JobRunStatus.Queued ||
            jobRun.status === JobRunStatus.Failed) &&
            onEditParameters && (
               <PermissionButton
                  allowedPermissionClaims={[PERMISSION_CLAIMS.JOBS_UPDATE]}
                  type="text"
                  icon={<EditOutlined />}
                  size="small"
                  onClick={handleEditParameters}
                  tooltipWhenEnabled="Edit Parameters"
                  useNativeTooltip={true}
               />
            )}
         {(jobRun.status === JobRunStatus.Queued ||
            jobRun.status === JobRunStatus.Dispatched ||
            jobRun.status === JobRunStatus.Running) && (
            <PermissionButton
               allowedPermissionClaims={[PERMISSION_CLAIMS.JOBS_UPDATE]}
               type="text"
               icon={<StopOutlined />}
               size="small"
               danger
               onClick={handleCancel}
               tooltipWhenEnabled="Cancel Job"
               useNativeTooltip={true}
            />
         )}
      </Space>
   );
};

export default JobRunActions;
