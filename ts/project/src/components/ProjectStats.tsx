import type { ApiErrorResult } from "@kontext-labs/common";
import { formatDuration, formatFileSize } from "@kontext-labs/common";
import { ChatService } from "@kontext-labs/chat";
import {
   ClockCircleOutlined,
   DatabaseOutlined,
   FileOutlined,
   SparklesOutlined
} from "@kontext-labs/icons";
import { useDataService } from "@kontext-labs/app-runtime/hooks";
import type {
   ProjectModel,
   ProjectStatsModel,
   ProjectTokenUsageResponse
} from "@kontext-labs/schema";
import {
   Divider,
   Flex,
   Progress,
   Space,
   Statistic,
   theme,
   Typography
} from "antd";
import React, { useEffect, useMemo, useState } from "react";
import { DataProjectService } from "../DataProjectService";
import ProjectTokenUsageChart from "./ProjectTokenUsageChart";

const { Text } = Typography;
const { useToken } = theme;

export interface ProjectStatsProps {
   projectId: string;
   project: ProjectModel;
   errorHandler?: (errorResult: ApiErrorResult) => Promise<void>;
}

const ProjectStats: React.FC<ProjectStatsProps> = ({
   projectId,
   project,
   errorHandler
}) => {
   const [loading, setLoading] = useState(true);
   const [stats, setStats] = useState<ProjectStatsModel | null>(null);
   const [tokenUsage, setTokenUsage] =
      useState<ProjectTokenUsageResponse | null>(null);
   const { token } = useToken();
   const projectService = useDataService(DataProjectService, errorHandler);
   const aiService = useDataService(ChatService, errorHandler);

   useEffect(() => {
      const fetchData = async () => {
         setLoading(true);
         try {
            const [statsRes, usageRes] = await Promise.all([
               projectService.getProjectStats(projectId),
               aiService.getProjectTokenUsage(projectId)
            ]);

            if (statsRes.succeed && statsRes.data) {
               setStats(statsRes.data);
            } else {
               setStats(null);
               console.error("Failed to fetch project stats:", statsRes.error);
            }

            if (usageRes.succeed && usageRes.data) {
               setTokenUsage(usageRes.data);
            }
         } catch (fetchError) {
            console.error("Failed to fetch project data:", fetchError);
         } finally {
            setLoading(false);
         }
      };

      void fetchData();
   }, [aiService, projectId, projectService]);

   const {
      usagePercentage,
      totalAllocationBytes,
      availableBytes,
      currentUsageBytes
   } = useMemo(() => {
      const totalAllocation =
         project.configuration?.totalStorageAllocationBytes ?? 0;
      const usage = stats?.totalSizeInBytes ?? 0;
      const usageClipped = Math.min(usage, totalAllocation);
      const percentage =
         totalAllocation > 0 ? (usageClipped / totalAllocation) * 100 : 0;
      const available = Math.max(0, totalAllocation - usage);

      return {
         usagePercentage: percentage,
         totalAllocationBytes: totalAllocation,
         availableBytes: available,
         currentUsageBytes: usage
      };
   }, [
      project.configuration?.totalStorageAllocationBytes,
      stats?.totalSizeInBytes
   ]);

   const getProgressStatus = () => {
      if (usagePercentage >= 95) return "exception";
      if (usagePercentage >= 80) return "normal";
      return "active";
   };

   const getStrokeColor = () => {
      if (usagePercentage >= 95) return token.colorError;
      if (usagePercentage >= 80) return token.colorWarning;
      return token.colorSuccess;
   };

   if (loading) {
      return <div>Loading...</div>;
   }

   return (
      <Space orientation="vertical" size="large" style={{ width: "100%" }}>
         <Flex wrap="wrap" gap="large">
            <Statistic
               title="Total Files"
               value={stats?.fileCount ?? 0}
               prefix={<FileOutlined />}
            />
            <Statistic
               title="Total Job Run Duration"
               value={
                  stats?.totalJobRunDurationMs
                     ? formatDuration(stats.totalJobRunDurationMs)
                     : "0s"
               }
               prefix={<ClockCircleOutlined />}
            />
            <Statistic
               title="Total Used Tokens"
               value={tokenUsage?.totalTokens ?? 0}
               prefix={<SparklesOutlined />}
            />
         </Flex>

         <Divider style={{ margin: "12px 0" }} />

         <Space orientation="vertical" size="small" style={{ width: "100%" }}>
            <Space
               align="center"
               style={{ width: "100%", justifyContent: "space-between" }}
            >
               <Space align="center">
                  <DatabaseOutlined
                     style={{ color: token.colorPrimary, fontSize: "16px" }}
                  />
                  <Text strong style={{ fontSize: "16px" }}>
                     Storage Usage
                  </Text>
               </Space>
               <Text
                  type="secondary"
                  style={{ fontSize: "12px", fontFamily: "monospace" }}
               >
                  {usagePercentage.toFixed(1)}%
               </Text>
            </Space>

            <Progress
               percent={usagePercentage}
               status={getProgressStatus()}
               strokeColor={getStrokeColor()}
               showInfo={false}
               size="small"
            />

            <Space
               orientation="vertical"
               size="small"
               style={{ width: "100%" }}
            >
               <Space
                  style={{ width: "100%", justifyContent: "space-between" }}
               >
                  <Text type="secondary" style={{ fontSize: "12px" }}>
                     Used:
                  </Text>
                  <Text style={{ fontSize: "12px", fontFamily: "monospace" }}>
                     {formatFileSize(currentUsageBytes)}
                  </Text>
               </Space>

               <Space
                  style={{ width: "100%", justifyContent: "space-between" }}
               >
                  <Text type="secondary" style={{ fontSize: "12px" }}>
                     Available:
                  </Text>
                  <Text style={{ fontSize: "12px", fontFamily: "monospace" }}>
                     {formatFileSize(availableBytes)}
                  </Text>
               </Space>

               <Space
                  style={{ width: "100%", justifyContent: "space-between" }}
               >
                  <Text type="secondary" style={{ fontSize: "12px" }}>
                     Total:
                  </Text>
                  <Text style={{ fontSize: "12px", fontFamily: "monospace" }}>
                     {formatFileSize(totalAllocationBytes)}
                  </Text>
               </Space>
            </Space>

            {usagePercentage >= 95 && (
               <Text type="danger" style={{ fontSize: "11px" }}>
                  Storage almost full
               </Text>
            )}
            {usagePercentage >= 80 && usagePercentage < 95 && (
               <Text style={{ fontSize: "11px", color: token.colorWarning }}>
                  Storage usage high
               </Text>
            )}
         </Space>

         <Divider style={{ margin: "24px 0 12px 0" }} />
         <ProjectTokenUsageChart
            projectId={projectId}
            initialData={tokenUsage}
            errorHandler={errorHandler}
         />
      </Space>
   );
};

export default ProjectStats;
