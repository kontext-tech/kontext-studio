import { getEventTypeConfig } from "../utils/eventTypeUtils";
import type { EventType } from "@kontext-tech/schema";
import { Space, Tag, Typography } from "antd";
import React from "react";
import { getEventIcon } from "./EventIcons";

interface EventTypeDisplayProps {
   type: EventType | undefined;
   showIcon?: boolean;
   showAsTag?: boolean;
   size?: "small" | "default" | "large";
}

const EventTypeDisplay: React.FC<EventTypeDisplayProps> = ({
   type,
   showIcon = true,
   showAsTag = false,
   size = "default"
}) => {
   const config = getEventTypeConfig(type);
   const text = config.displayName;

   if (showAsTag) {
      return (
         <Tag
            style={{
               fontSize:
                  size === "small"
                     ? "12px"
                     : size === "large"
                       ? "16px"
                       : "14px",
               display: "inline-flex",
               alignItems: "center",
               gap: "4px"
            }}
         >
            {showIcon && (
               <span
                  style={{
                     fontSize:
                        size === "small"
                           ? "10px"
                           : size === "large"
                             ? "14px"
                             : "12px"
                  }}
               >
                  {getEventIcon(type)}
               </span>
            )}
            {text}
         </Tag>
      );
   }

   if (showIcon) {
      return (
         <Space size="small" align="center">
            <span
               style={{
                  fontSize:
                     size === "small"
                        ? "12px"
                        : size === "large"
                          ? "16px"
                          : "14px"
               }}
            >
               {getEventIcon(type)}
            </span>
            <Typography.Text
               style={{
                  fontSize:
                     size === "small"
                        ? "12px"
                        : size === "large"
                          ? "16px"
                          : "14px"
               }}
            >
               {text}
            </Typography.Text>
         </Space>
      );
   }

   return (
      <Typography.Text
         style={{
            fontSize:
               size === "small" ? "12px" : size === "large" ? "16px" : "14px"
         }}
      >
         {text}
      </Typography.Text>
   );
};

export default EventTypeDisplay;
