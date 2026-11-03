import { LoadingSpinner } from "@kontext-tech/ui";
import {
   BugOutlined,
   CloseCircleOutlined,
   ExclamationCircleOutlined,
   InfoCircleOutlined,
   QuestionCircleOutlined,
   WarningOutlined
} from "@kontext-tech/icons";
import { LogLevel, type JobRunLogModel } from "@kontext-tech/schema";
import { Flex, Typography, theme } from "antd";
import dayjs from "dayjs";
import React from "react";

const { Text, Paragraph } = Typography;

interface JobRunLogsListProps {
   logs: JobRunLogModel[];
   loading: boolean;
   height?: number | null;
}

const JobRunLogsList: React.FC<JobRunLogsListProps> = ({
   logs,
   loading,
   height
}) => {
   const { token } = theme.useToken();
   const containerHeight = height ? `${height}px` : undefined;

   const getLogLevelIcon = (level?: LogLevel) => {
      const iconStyle = { fontSize: "14px" };

      switch (level) {
         case LogLevel.Trace:
            return (
               <BugOutlined
                  style={{ ...iconStyle, color: token.colorPrimary }}
               />
            );
         case LogLevel.Debug:
            return (
               <BugOutlined style={{ ...iconStyle, color: token.colorInfo }} />
            );
         case LogLevel.Information:
            return (
               <InfoCircleOutlined
                  style={{ ...iconStyle, color: token.colorTextSecondary }}
               />
            );
         case LogLevel.Warning:
            return (
               <WarningOutlined
                  style={{ ...iconStyle, color: token.colorWarning }}
               />
            );
         case LogLevel.Error:
            return (
               <CloseCircleOutlined
                  style={{ ...iconStyle, color: token.colorError }}
               />
            );
         case LogLevel.Critical:
            return (
               <ExclamationCircleOutlined
                  style={{ ...iconStyle, color: token.colorError }}
               />
            );
         default:
            return (
               <QuestionCircleOutlined
                  style={{ ...iconStyle, color: token.colorTextTertiary }}
               />
            );
      }
   };

   return (
      <Flex
         vertical
         style={{
            height: containerHeight,
            minHeight: 0,
            overflow: "auto",
            padding: "4px 6px",
            border: `1px solid ${token.colorBorderSecondary}`,
            borderRadius: token.borderRadiusLG
         }}
      >
         {loading ? (
            <Flex
               vertical
               align="center"
               justify="center"
               style={{
                  flex: 1,
                  minHeight: 120,
                  textAlign: "center"
               }}
            >
               <LoadingSpinner />
               <div style={{ marginTop: 8 }}>Loading logs...</div>
            </Flex>
         ) : logs.length === 0 ? (
            <Flex
               align="center"
               justify="center"
               style={{
                  flex: 1,
                  minHeight: 120
               }}
            >
               <Text type="secondary">No logs available.</Text>
            </Flex>
         ) : (
            logs.map((log, index) => (
               <Flex
                  key={index}
                  gap={8}
                  align="flex-start"
                  style={{ padding: "4px 0" }}
               >
                  {log.level !== undefined && (
                     <div
                        style={{
                           display: "flex",
                           alignItems: "center",
                           justifyContent: "center",
                           width: "24px",
                           height: "24px",
                           flexShrink: 0
                        }}
                     >
                        {getLogLevelIcon(log.level)}
                     </div>
                  )}
                  <Flex vertical flex={1}>
                     <span
                        style={{
                           fontSize: "11px",
                           color: token.colorTextSecondary
                        }}
                     >
                        {dayjs(log.timestamp).format("YYYY-MM-DD HH:mm:ss.SSS")}
                     </span>
                     <Text>{log.message}</Text>
                     {log.data && (
                        <Paragraph
                           code
                           copyable
                           style={{
                              marginTop: 4,
                              marginBottom: 0,
                              fontSize: "10px",
                              lineHeight: "1.2"
                           }}
                        >
                           {log.data}
                        </Paragraph>
                     )}
                  </Flex>
               </Flex>
            ))
         )}
      </Flex>
   );
};

export default JobRunLogsList;
