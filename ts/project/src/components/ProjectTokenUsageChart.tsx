import type { ChartConfig } from "@kontext-tech/chart";
import { ChartFactory } from "@kontext-tech/chart";
import { ChatService } from "@kontext-tech/chat";
import type { ApiErrorResult } from "@kontext-tech/common";
import { useDataService } from "@kontext-tech/app-runtime/hooks";
import type {
   ProjectDailyTokenUsageResponse,
   ProjectTokenUsageResponse
} from "@kontext-tech/schema";
import { useTheme } from "@kontext-tech/theme";
import { LoadingSpinner } from "@kontext-tech/ui";
import { Empty, Flex, Space, Typography } from "antd";
import React, { useEffect, useMemo, useState } from "react";

const { Text } = Typography;

export interface ProjectTokenUsageChartProps {
   projectId: string;
   initialData?: ProjectTokenUsageResponse | null;
   errorHandler?: (errorResult: ApiErrorResult) => Promise<void>;
}

const ProjectTokenUsageChart: React.FC<ProjectTokenUsageChartProps> = ({
   projectId,
   initialData,
   errorHandler
}) => {
   const [loading, setLoading] = useState(!initialData);
   const [usageData, setUsageData] = useState<ProjectTokenUsageResponse | null>(
      initialData || null
   );
   const [dailyUsageData, setDailyUsageData] =
      useState<ProjectDailyTokenUsageResponse | null>(null);
   const { isDarkMode } = useTheme();

   const aiService = useDataService(ChatService, errorHandler);

   useEffect(() => {
      const fetchUsage = async () => {
         if (!initialData) {
            setLoading(true);
         }

         try {
            const [monthlyResp, dailyResp] = await Promise.all([
               !initialData
                  ? aiService.getProjectTokenUsage(projectId)
                  : Promise.resolve(null),
               aiService.getProjectDailyTokenUsage(projectId)
            ]);

            if (monthlyResp?.succeed && monthlyResp.data) {
               setUsageData(monthlyResp.data);
            }
            if (dailyResp.succeed && dailyResp.data) {
               setDailyUsageData(dailyResp.data);
            }
         } catch (fetchError) {
            console.error("Failed to fetch token usage:", fetchError);
         } finally {
            if (!initialData) {
               setLoading(false);
            }
         }
      };

      void fetchUsage();
   }, [aiService, initialData, projectId]);

   const chartConfig = useMemo(() => {
      if (!usageData?.usages?.length) {
         return null;
      }

      const data = [...usageData.usages]
         .sort((a, b) => (a.month || "").localeCompare(b.month || ""))
         .flatMap((usage) => [
            {
               month: usage.month,
               direction: "Inbound",
               value: usage.inboundTokens ?? 0
            },
            {
               month: usage.month,
               direction: "Outbound",
               value: usage.outboundTokens ?? 0
            }
         ]);

      return {
         chartType: "column" as const,
         data,
         xField: "month",
         yField: "value",
         colorField: "direction",
         aggregate: "sum",
         stack: true,
         height: 350,
         colorPalette: "kontext" as const,
         title: "Monthly Token Usage History",
         legend: {
            position: "bottom"
         }
      } as ChartConfig;
   }, [usageData]);

   const dailyChartConfig = useMemo(() => {
      if (!dailyUsageData?.usages?.length) {
         return null;
      }

      const data = [...dailyUsageData.usages]
         .sort((a, b) => (a.day || "").localeCompare(b.day || ""))
         .flatMap((usage) => [
            {
               day: usage.day,
               direction: "Inbound",
               value: usage.inboundTokens ?? 0
            },
            {
               day: usage.day,
               direction: "Outbound",
               value: usage.outboundTokens ?? 0
            }
         ]);

      return {
         chartType: "column" as const,
         data,
         xField: "day",
         yField: "value",
         colorField: "direction",
         aggregate: "sum",
         stack: true,
         height: 350,
         colorPalette: "kontext" as const,
         title: `Daily Usage (${dailyUsageData.month})`,
         legend: {
            position: "bottom"
         }
      } as ChartConfig;
   }, [dailyUsageData]);

   const modelPieConfig = useMemo<ChartConfig | null>(() => {
      if (!usageData?.usages?.length) return null;

      const data = usageData.usages.map((usage) => ({
         model:
            usage.modelDisplayName || usage.canonicalModelId || "Unknown model",
         value: usage.totalTokens || 0
      }));

      return {
         chartType: "pie" as const,
         data,
         angleField: "value",
         colorField: "model",
         aggregate: "sum",
         height: 350,
         title: "Usage by Model",
         colorPalette: "kontext" as const
      } as ChartConfig;
   }, [usageData]);

   const directionPieConfig = useMemo<ChartConfig | null>(() => {
      if (!usageData?.usages?.length) return null;

      const data = usageData.usages.flatMap((usage) => [
         { direction: "Inbound", value: usage.inboundTokens ?? 0 },
         { direction: "Outbound", value: usage.outboundTokens ?? 0 }
      ]);

      return {
         chartType: "pie" as const,
         data,
         angleField: "value",
         colorField: "direction",
         aggregate: "sum",
         height: 350,
         title: "Inbound vs Outbound",
         colorPalette: "kontext" as const
      } as ChartConfig;
   }, [usageData]);

   if (loading) {
      return (
         <div style={{ textAlign: "center", padding: "40px" }}>
            <LoadingSpinner size="large" />
         </div>
      );
   }

   if (!usageData?.usages?.length) {
      return (
         <Empty description="No token usage data available for this project." />
      );
   }

   return (
      <Flex vertical gap={48} style={{ width: "100%", padding: "16px 0" }}>
         {dailyChartConfig && (
            <div style={{ height: 400 }}>
               <ChartFactory
                  config={dailyChartConfig}
                  isDarkMode={isDarkMode}
                  showExport={true}
               />
            </div>
         )}

         {chartConfig && (
            <div style={{ height: 400 }}>
               <ChartFactory
                  config={chartConfig}
                  isDarkMode={isDarkMode}
                  showExport={true}
               />
            </div>
         )}

         <Flex gap={48}>
            {modelPieConfig && (
               <div style={{ flex: 1, height: 400 }}>
                  <ChartFactory
                     config={modelPieConfig}
                     isDarkMode={isDarkMode}
                     showExport={true}
                  />
               </div>
            )}

            {directionPieConfig && (
               <div style={{ flex: 1, height: 400 }}>
                  <ChartFactory
                     config={directionPieConfig}
                     isDarkMode={isDarkMode}
                     showExport={true}
                  />
               </div>
            )}
         </Flex>

         <Space separator={<Text type="secondary">|</Text>}>
            <Text type="secondary">
               Total Inbound:{" "}
               <strong>{usageData.totalInboundTokens?.toLocaleString()}</strong>
            </Text>
            <Text type="secondary">
               Total Outbound:{" "}
               <strong>
                  {usageData.totalOutboundTokens?.toLocaleString()}
               </strong>
            </Text>
            <Text type="secondary">
               Total Tokens:{" "}
               <strong>{usageData.totalTokens?.toLocaleString()}</strong>
            </Text>
         </Space>
      </Flex>
   );
};

export default ProjectTokenUsageChart;
