import { CodeOutlined } from "@kontext-tech/icons";
import type { JobExecutionRuntime } from "@kontext-tech/schema";
import { JobExecutionRuntime as JobExecutionRuntimeEnum } from "@kontext-tech/schema";
import { Tag } from "antd";
import React from "react";

interface RuntimeBadgeProps {
   runtime?: JobExecutionRuntime;
   size?: "small" | "default";
}

const RuntimeBadge: React.FC<RuntimeBadgeProps> = ({
   runtime,
   size = "default"
}) => {
   if (!runtime) return null;

   const getRuntimeConfig = (executionRuntime: JobExecutionRuntime) => {
      switch (executionRuntime) {
         case JobExecutionRuntimeEnum.DotNet:
            return {
               color: "#512BD4",
               icon: <CodeOutlined />,
               text: "C#"
            };
         case JobExecutionRuntimeEnum.Python:
            return {
               color: "#3776ab",
               icon: <CodeOutlined />,
               text: "Py"
            };
         default:
            return {
               color: "default",
               icon: <CodeOutlined />,
               text: executionRuntime
            };
      }
   };

   const config = getRuntimeConfig(runtime);

   return (
      <Tag
         color={config.color}
         icon={config.icon}
         style={{
            fontSize: size === "small" ? "11px" : "12px",
            lineHeight: size === "small" ? "14px" : "16px"
         }}
      >
         {config.text}
      </Tag>
   );
};

export default RuntimeBadge;
