import { PermissionButton } from "@kontext-labs/auth";
import { PERMISSION_CLAIMS } from "@kontext-labs/auth";
import {
   DeleteOutlined,
   EditOutlined,
   PlayCircleOutlined,
   StopOutlined
} from "@kontext-labs/icons";
import { Space } from "antd";
import React from "react";
import type { JobActionsProps } from "../jobTypes";

const JobActions: React.FC<JobActionsProps> = ({
   job,
   ui,
   onEdit,
   onDelete,
   onSchedule,
   onDisableSchedule
}) => {
   const isSystemJob = !job.ownerId;

   return (
      <Space size="small">
         <PermissionButton
            allowedPermissionClaims={[PERMISSION_CLAIMS.JOBS_EXECUTE]}
            type="text"
            icon={<PlayCircleOutlined />}
            onClick={() => onSchedule(job.id!, job.name!)}
            size="small"
            disabled={!job.isEnabled || isSystemJob}
            tooltipWhenEnabled={job.isEnabled ? "Run Job" : undefined}
            tooltipWhenDisabled={
               isSystemJob
                  ? "System jobs cannot be run manually"
                  : "Job must be enabled to run"
            }
            useNativeTooltip={true}
         />
         <PermissionButton
            allowedPermissionClaims={[PERMISSION_CLAIMS.JOBS_UPDATE]}
            type="text"
            icon={<StopOutlined />}
            size="small"
            disabled={!job.schedule || isSystemJob}
            tooltipWhenEnabled={job.schedule ? "Disable schedule" : undefined}
            tooltipWhenDisabled={
               isSystemJob
                  ? "System jobs cannot be modified"
                  : "No schedule to disable"
            }
            useNativeTooltip={true}
            onClick={() => {
               ui.confirm({
                  title: "Disable Schedule",
                  content: `Stop automatic runs for "${job.name}" by clearing its schedule?`,
                  okText: "Disable",
                  cancelText: "Cancel",
                  onOk: () => onDisableSchedule(job)
               });
            }}
         />
         <PermissionButton
            allowedPermissionClaims={[PERMISSION_CLAIMS.JOBS_UPDATE]}
            type="text"
            icon={<EditOutlined />}
            onClick={() => onEdit(job)}
            size="small"
            disabled={isSystemJob}
            tooltipWhenEnabled="Edit Job"
            tooltipWhenDisabled="System jobs cannot be edited"
            useNativeTooltip={true}
         />
         <PermissionButton
            allowedPermissionClaims={[PERMISSION_CLAIMS.JOBS_DELETE]}
            type="text"
            icon={<DeleteOutlined />}
            danger
            size="small"
            disabled={isSystemJob}
            tooltipWhenEnabled="Delete Job"
            tooltipWhenDisabled="System jobs cannot be deleted"
            useNativeTooltip={true}
            onClick={() => {
               ui.confirm({
                  title: "Delete Job",
                  content: `Are you sure you want to delete "${job.name}"?`,
                  onOk: () => onDelete(job.id!, job.name!),
                  okText: "Yes",
                  cancelText: "No",
                  okButtonProps: { danger: true }
               });
            }}
         />
      </Space>
   );
};

export default JobActions;
