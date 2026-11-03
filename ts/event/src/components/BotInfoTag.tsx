import { RobotOutlined, UserOutlined } from "@kontext-labs/icons";
import { Tag, Tooltip } from "antd";
import React from "react";

interface BotInfoTagProps {
   isBot: boolean;
   botType?: string | null;
   botName?: string | null;
}

const BotInfoTag: React.FC<BotInfoTagProps> = ({ isBot, botType, botName }) => {
   if (!isBot) {
      return (
         <Tooltip title="Human User">
            <Tag color="green" icon={<UserOutlined />}>
               Human
            </Tag>
         </Tooltip>
      );
   }

   const getBotColor = (type?: string | null): string => {
      if (!type) return "orange";

      switch (type.toLowerCase()) {
         case "search engine":
            return "blue";
         case "social media":
            return "purple";
         case "seo tool":
            return "gold";
         case "monitoring":
            return "cyan";
         case "crawler":
         case "spider":
            return "geekblue";
         case "tool":
            return "lime";
         default:
            return "orange";
      }
   };

   const tooltipContent = (
      <div>
         <div>
            <strong>Bot Type:</strong> {botType || "Unknown"}
         </div>
         {botName && (
            <div>
               <strong>Bot Name:</strong> {botName}
            </div>
         )}
      </div>
   );

   return (
      <Tooltip title={tooltipContent}>
         <Tag color={getBotColor(botType)} icon={<RobotOutlined />}>
            {botName || botType || "Bot"}
         </Tag>
      </Tooltip>
   );
};

export default BotInfoTag;
