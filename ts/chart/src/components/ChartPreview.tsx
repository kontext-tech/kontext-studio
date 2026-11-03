import type { TabularData } from "@kontext-tech/schema";
import { Alert, Card, Tabs, theme } from "antd";
import React from "react";
import type { ChartConfig } from "../types/chart";
import { ChartFactory } from "./ChartFactory";

const { useToken } = theme;

// Chart configuration state type for the component
export interface ChartPreviewProps {
   /** Chart configuration data containing all necessary information */
   chartConfig: ChartConfig | null;
   /** Whether to show tabs or just preview */
   showTabs?: boolean;
   /** Dark mode flag */
   isDarkMode?: boolean;
   /** Whether to show export button */
   showExport?: boolean;
}

/**
 * Chart Preview Component
 *
 * Displays chart preview and optionally configuration code
 */
export const ChartPreview: React.FC<ChartPreviewProps> = ({
   chartConfig,
   showTabs = true,
   isDarkMode = false,
   showExport = true
}) => {
   const { token } = useToken();
   const chartData: TabularData | undefined = chartConfig?.data;

   // Generate the configuration object to display in code
   const generateCodeConfiguration = (): ChartConfig | null => {
      if (!chartConfig) return null;
      // Remove data to avoid huge dumps
      const codeConfig = { ...chartConfig, data: undefined };
      return codeConfig;
   };

   // Convert ChartConfig to renderable format
   const getChartConfigForRendering = (): ChartConfig | null => {
      if (!chartConfig) return null;

      // Use fetched data instead of data from config
      const directConfig: ChartConfig = {
         ...chartConfig,
         data: chartData,
         height: chartConfig.height || 400
      };

      return directConfig;
   };

   const renderableChartConfig = getChartConfigForRendering();

   const previewContent =
      !renderableChartConfig || !chartData ? (
         <Alert
            title="Configure Chart Fields"
            description="Please select the required data fields in the configuration panel to see the chart preview."
            type="info"
            banner
            showIcon
         />
      ) : (
         <div
            key={`chart-${renderableChartConfig.chartType}-${
               renderableChartConfig.colorPalette || "default"
            }`}
         >
            <ChartFactory
               config={renderableChartConfig}
               isDarkMode={isDarkMode}
               showExport={showExport}
            />
         </div>
      );

   // If showTabs is false, just return the preview content
   if (!showTabs) {
      return previewContent;
   }

   const codeContent = (
      <>
         <Card
            size="small"
            styles={{
               body: {
                  padding: token.paddingXS
               }
            }}
         >
            <pre
               style={{
                  margin: 0,
                  width: "100%",
                  fontSize: token.fontSizeSM,
                  lineHeight: 1.5,
                  color: token.colorText,
                  fontFamily: "monospace",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word",
                  maxHeight: 300
               }}
            >
               {JSON.stringify(generateCodeConfiguration(), null, 2)}
            </pre>
         </Card>
      </>
   );

   return (
      <Tabs
         defaultActiveKey="preview"
         size="small"
         style={{ height: "100%" }}
         tabBarStyle={{
            margin: 0,
            padding: `0 ${token.paddingSM}px`
         }}
         items={[
            {
               key: "preview",
               label: "Preview",
               children: (
                  <div style={{ padding: token.paddingSM }}>
                     {previewContent}
                  </div>
               )
            },
            {
               key: "code",
               label: "Code",
               children: (
                  <div style={{ padding: token.paddingSM }}>{codeContent}</div>
               )
            }
         ]}
      />
   );
};
