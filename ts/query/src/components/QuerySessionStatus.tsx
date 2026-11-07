import { QuerySessionStatus } from "@kontext-tech/schema";
import { Tag } from "antd";
import type { CSSProperties } from "react";
import React from "react";

export interface QuerySessionStatusProps {
   status: QuerySessionStatus;
   size?: "small" | "default";
   style?: CSSProperties;
}

/**
 * A dedicated component for displaying query session status with appropriate colors and text.
 * Provides consistent status representation across the application.
 */
const QuerySessionStatusComponent: React.FC<QuerySessionStatusProps> = ({
   status,
   size = "default",
   style
}) => {
   const getStatusColor = (status: QuerySessionStatus): string => {
      switch (status) {
         case QuerySessionStatus.Active:
            return "green";
         case QuerySessionStatus.Initializing:
            return "blue";
         case QuerySessionStatus.Error:
            return "red";
         case QuerySessionStatus.Closed:
            return "default";
         case QuerySessionStatus.Deleted:
            return "red";
         default:
            return "default";
      }
   };

   const getStatusText = (status: QuerySessionStatus): string => {
      switch (status) {
         case QuerySessionStatus.Active:
            return "Active";
         case QuerySessionStatus.Initializing:
            return "Initializing";
         case QuerySessionStatus.Error:
            return "Error";
         case QuerySessionStatus.Closed:
            return "Closed";
         case QuerySessionStatus.Deleted:
            return "Deleted";
         default:
            return "Unknown";
      }
   };

   return (
      <Tag
         color={getStatusColor(status)}
         style={{
            fontSize: size === "small" ? "10px" : "12px",
            padding: size === "small" ? "2px 4px" : "4px 8px",
            borderRadius: "4px",
            ...style
         }}
      >
         {getStatusText(status)}
      </Tag>
   );
};

export default QuerySessionStatusComponent;
