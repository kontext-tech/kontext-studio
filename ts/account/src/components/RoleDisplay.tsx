import {
   SYSTEM_ROLE_COLORS,
   SYSTEM_ROLE_DISPLAY_NAMES,
   SYSTEM_ROLES,
   type SystemRole
} from "@kontext-labs/auth";
import { SafetyOutlined } from "@kontext-labs/icons";
import { Space, Tag, Typography } from "antd";
import React from "react";

interface RoleDisplayProps {
   /**
    * The roles to display
    */
   roles?: string[];

   /**
    * Whether to show a message when no roles are assigned
    * @default true
    */
   showEmptyMessage?: boolean;

   /**
    * Custom empty message text
    * @default "No roles assigned"
    */
   emptyMessage?: string;

   /**
    * The orientation of the roles list
    * @default "horizontal"
    */
   orientation?: "horizontal" | "vertical";

   /**
    * Custom class name for the container
    */
   className?: string;
}

/**
 * A component for displaying user roles with appropriate styling
 */
const RoleDisplay: React.FC<RoleDisplayProps> = ({
   roles = [],
   showEmptyMessage = true,
   emptyMessage = "No roles assigned",
   orientation = "horizontal",
   className
}) => {
   // If no roles and we don't want to show an empty message, render nothing
   if (!roles.length && !showEmptyMessage) {
      return null;
   }

   // Determine if orientation is vertical
   const isVertical = orientation === "vertical";

   return (
      <div className={className}>
         {roles.length > 0 ? (
            <Space
               size={[0, 4]}
               wrap={!isVertical}
               orientation={orientation}
               style={{ width: isVertical ? "100%" : undefined }}
            >
               {roles.map((role) => {
                  // Check if this is a system role
                  const isSystemRole = Object.values(SYSTEM_ROLES).includes(
                     role as SystemRole
                  );
                  const color = isSystemRole
                     ? SYSTEM_ROLE_COLORS[role as SystemRole] || "blue"
                     : "default";

                  return (
                     <Tag
                        key={role}
                        color={color}
                        icon={isSystemRole ? <SafetyOutlined /> : null}
                        style={{
                           maxWidth: "200px",
                           overflow: "hidden",
                           textOverflow: "ellipsis",
                           whiteSpace: "nowrap"
                        }}
                        title={
                           isSystemRole
                              ? SYSTEM_ROLE_DISPLAY_NAMES[role as SystemRole]
                              : role
                        }
                     >
                        {isSystemRole
                           ? SYSTEM_ROLE_DISPLAY_NAMES[role as SystemRole]
                           : role}
                     </Tag>
                  );
               })}
            </Space>
         ) : showEmptyMessage ? (
            <Typography.Text type="secondary">{emptyMessage}</Typography.Text>
         ) : null}
      </div>
   );
};

export default RoleDisplay;
