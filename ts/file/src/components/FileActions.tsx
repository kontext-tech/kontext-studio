import {
   DeleteOutlined,
   DownloadOutlined,
   EyeOutlined,
   InfoCircleOutlined
} from "@kontext-tech/icons";
import { CommonRoleGroups, PermissionContext } from "@kontext-tech/auth";
import { type FileModel } from "@kontext-tech/schema";
import { Button, Space, Tooltip } from "antd";
import { useContext } from "react";
import { isImageResource } from "../utils/fileUtils";

export interface FileActionsProps {
   file: FileModel;
   onDownload: (file: FileModel) => void;
   onPreview?: (file: FileModel) => void;
   onViewDetails?: (file: FileModel) => void;
   onDelete?: (file: FileModel) => void;
   showPreview?: boolean;
   showViewDetails?: boolean;
   showDelete?: boolean;
   size?: "small" | "middle" | "large";
   canDownload?: boolean;
   canViewDetails?: boolean;
   canDelete?: boolean;
   usePermissions?: boolean;
   downloadDisabledReason?: string;
   viewDetailsDisabledReason?: string;
   deleteDisabledReason?: string;
}

const FileActions = ({
   file,
   onDownload,
   onPreview,
   onViewDetails,
   onDelete,
   showPreview = true,
   showViewDetails = false,
   showDelete = false,
   size = "small",
   canDownload,
   canViewDetails,
   canDelete,
   usePermissions = false,
   downloadDisabledReason,
   viewDetailsDisabledReason,
   deleteDisabledReason
}: FileActionsProps) => {
   const permissionContext = useContext(PermissionContext);
   const showPreviewButton = showPreview && isImageResource(file) && onPreview;
   const isAuthenticated = permissionContext?.isAuthenticated ?? false;
   const resolvedCanDownload =
      canDownload ??
      (!usePermissions
         ? true
         : Boolean(
              permissionContext?.hasPermission({
                 allowedProjectRoles: CommonRoleGroups.ALL_USERS
              })
           ));
   const resolvedCanViewDetails =
      canViewDetails ??
      (!usePermissions
         ? true
         : Boolean(
              permissionContext?.hasPermission({
                 allowedProjectRoles: CommonRoleGroups.ALL_USERS
              })
           ));
   const resolvedCanDelete =
      canDelete ??
      (!usePermissions
         ? true
         : Boolean(
              permissionContext?.hasPermission({
                 allowedProjectRoles: CommonRoleGroups.CONTENT_EDITORS
              })
           ));
   const authRequiredReason = isAuthenticated
      ? undefined
      : "You need to sign in to access this action";

   return (
      <Space size="small">
         {showPreviewButton && (
            <Button
               size={size}
               icon={<EyeOutlined />}
               onClick={() => onPreview(file)}
               type="text"
               title="Preview"
            />
         )}
         {!isImageResource(file) && (
            <Tooltip
               title={
                  !resolvedCanDownload
                     ? downloadDisabledReason ||
                       authRequiredReason ||
                       "You need appropriate permissions to download files"
                     : undefined
               }
            >
               <Button
                  size={size}
                  icon={<DownloadOutlined />}
                  onClick={() => onDownload(file)}
                  type="text"
                  title="Download"
                  disabled={!resolvedCanDownload}
               />
            </Tooltip>
         )}
         {showViewDetails && onViewDetails && (
            <Tooltip
               title={
                  !resolvedCanViewDetails
                     ? viewDetailsDisabledReason ||
                       authRequiredReason ||
                       "You need appropriate permissions to view file details"
                     : undefined
               }
            >
               <Button
                  size={size}
                  icon={<InfoCircleOutlined />}
                  onClick={() => onViewDetails(file)}
                  type="text"
                  title="View details"
                  disabled={!resolvedCanViewDetails}
               />
            </Tooltip>
         )}
         {showDelete && onDelete && (
            <Tooltip
               title={
                  !resolvedCanDelete
                     ? deleteDisabledReason ||
                       authRequiredReason ||
                       "You need appropriate permissions to delete files"
                     : undefined
               }
            >
               <Button
                  size={size}
                  icon={<DeleteOutlined />}
                  onClick={() => onDelete(file)}
                  type="text"
                  title="Delete file"
                  danger
                  disabled={!resolvedCanDelete}
               />
            </Tooltip>
         )}
      </Space>
   );
};

export default FileActions;
