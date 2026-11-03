import { Select, Tooltip } from "antd";
import type { SelectProps } from "antd/es/select";
import type { ReactNode } from "react";
import { useRef } from "react";
import type { PermissionProps } from "../permissionTypes";
import PermissionGate from "./PermissionGate";

export interface PermissionSelectProps extends SelectProps, PermissionProps {
   tooltipWhenDisabled?: string;
   children?: ReactNode;
}

const PermissionSelect = ({
   allowedProjectRoles,
   allowedSystemRoles,
   allowedPermissionClaims,
   allowedUserIds,
   allowOnlyOwner,
   tooltipWhenDisabled = "You don't have permission to use this control",
   requireAuthenticated = false,
   children,
   ...props
}: PermissionSelectProps) => {
   const selectRef = useRef(null);

   const disabledSelect = (
      <Select ref={selectRef} {...props} disabled>
         {children}
      </Select>
   );

   const fallback = tooltipWhenDisabled ? (
      <Tooltip title={tooltipWhenDisabled}>{disabledSelect}</Tooltip>
   ) : (
      disabledSelect
   );

   return (
      <PermissionGate
         allowedProjectRoles={allowedProjectRoles}
         allowedSystemRoles={allowedSystemRoles}
         allowedPermissionClaims={allowedPermissionClaims}
         allowedUserIds={allowedUserIds}
         allowOnlyOwner={allowOnlyOwner}
         requireAuthenticated={requireAuthenticated}
         fallback={fallback}
      >
         <Select ref={selectRef} {...props}>
            {children}
         </Select>
      </PermissionGate>
   );
};

export default PermissionSelect;
