import React from "react";
import { MessageOutlined, SparklesOutlined } from "./lucide";
import { createIconFromName } from "./reactIconUtils";

export interface AgentIconProps {
   /**
    * Direct icon name override (e.g. from backend configuration).
    */
   icon?: string | null;
   style?: React.CSSProperties;
   className?: string;
}

export const AgentIcon: React.FC<AgentIconProps> = ({
   icon,
   style,
   className
}) => {
   const iconStyle: React.CSSProperties = {
      fontSize: "inherit",
      ...style
   };

   // 1. Try dynamic icon from prop
   if (icon) {
      const DynamicIcon = createIconFromName(icon, {
         style: iconStyle,
         className
      });
      if (DynamicIcon) {
         return <>{DynamicIcon}</>;
      }
   }

   if (!icon) {
      return <SparklesOutlined style={iconStyle} className={className} />;
   }

   return <MessageOutlined style={iconStyle} className={className} />;
};

export default AgentIcon;
