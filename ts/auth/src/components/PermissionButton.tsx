import type { PermissionProps } from "../permissionTypes";
import { Button, Tooltip } from "antd";
import type { ButtonProps } from "antd/es/button";
import { forwardRef } from "react";
import PermissionGate from "./PermissionGate";

interface PermissionButtonProps extends ButtonProps, PermissionProps {
   tooltipWhenDisabled?: string;
   tooltipWhenEnabled?: string;
   useNativeTooltip?: boolean;
}

const PermissionButton = forwardRef<HTMLButtonElement, PermissionButtonProps>(
   (
      {
         allowedProjectRoles,
         allowedSystemRoles,
         allowedPermissionClaims,
         tooltipWhenDisabled = "You don't have permission to perform this action",
         tooltipWhenEnabled,
         useNativeTooltip = false,
         requireAuthenticated = false,
         children,
         ...props
      },
      ref
   ) => {
      if (useNativeTooltip) {
         const enabledButton = (
            <Button ref={ref} {...props} title={tooltipWhenEnabled}>
               {children}
            </Button>
         );

         const disabledButton = (
            <Button ref={ref} {...props} disabled title={tooltipWhenDisabled}>
               {children}
            </Button>
         );

         return (
            <PermissionGate
               allowedProjectRoles={allowedProjectRoles}
               allowedSystemRoles={allowedSystemRoles}
               allowedPermissionClaims={allowedPermissionClaims}
               requireAuthenticated={requireAuthenticated}
               fallback={disabledButton}
            >
               {enabledButton}
            </PermissionGate>
         );
      }

      const enabledButton = (
         <Button ref={ref} {...props}>
            {children}
         </Button>
      );

      const wrappedEnabledButton = tooltipWhenEnabled ? (
         <Tooltip title={tooltipWhenEnabled}>{enabledButton}</Tooltip>
      ) : (
         enabledButton
      );

      const disabledButton = (
         <Button ref={ref} {...props} disabled>
            {children}
         </Button>
      );

      const fallback = tooltipWhenDisabled ? (
         <Tooltip title={tooltipWhenDisabled}>{disabledButton}</Tooltip>
      ) : (
         disabledButton
      );

      return (
         <PermissionGate
            allowedProjectRoles={allowedProjectRoles}
            allowedSystemRoles={allowedSystemRoles}
            allowedPermissionClaims={allowedPermissionClaims}
            requireAuthenticated={requireAuthenticated}
            fallback={fallback}
         >
            {wrappedEnabledButton}
         </PermissionGate>
      );
   }
);

PermissionButton.displayName = "PermissionButton";

export default PermissionButton;
