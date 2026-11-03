import { DebouncedSearch } from "@kontext-labs/ui";
import { Tooltip } from "antd";
import type { InputProps, InputRef } from "antd/es/input";
import { forwardRef } from "react";
import type { PermissionProps } from "../permissionTypes";
import PermissionGate from "./PermissionGate";

export interface PermissionSearchProps
   extends Omit<InputProps, "onChange">, PermissionProps {
   tooltipWhenDisabled?: string;
   onSearch: (value: string) => void;
   defaultValue?: string;
   value?: string;
   delay?: number;
}

const PermissionSearch = forwardRef<InputRef, PermissionSearchProps>(
   (
      {
         allowedProjectRoles,
         tooltipWhenDisabled = "You don't have permission to use search",
         requireAuthenticated = false,
         onSearch,
         defaultValue,
         value,
         delay,
         ...props
      },
      ref
   ) => {
      const disabledSearch = (
         <DebouncedSearch
            ref={ref}
            {...props}
            disabled
            onSearch={() => {}}
            value={value}
            defaultValue={defaultValue}
            delay={delay}
         />
      );

      const fallback = tooltipWhenDisabled ? (
         <Tooltip title={tooltipWhenDisabled}>{disabledSearch}</Tooltip>
      ) : (
         disabledSearch
      );

      return (
         <PermissionGate
            allowedProjectRoles={allowedProjectRoles}
            requireAuthenticated={requireAuthenticated}
            fallback={fallback}
         >
            <DebouncedSearch
               ref={ref}
               {...props}
               onSearch={onSearch}
               value={value}
               defaultValue={defaultValue}
               delay={delay}
            />
         </PermissionGate>
      );
   }
);

PermissionSearch.displayName = "PermissionSearch";

export default PermissionSearch;
