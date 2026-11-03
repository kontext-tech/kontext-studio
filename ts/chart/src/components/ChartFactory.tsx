import type { Chart } from "@ant-design/plots";
import type { TabularData } from "@kontext-labs/schema";
import { Alert, Card, Empty, Space, Spin, Typography, theme } from "antd";
import React, { useState } from "react";
import { convertChartConfig } from "../schemas/converters";
import { validateChartConfig as validateChart } from "../schemas/validation";
import type { ChartConfig, ChartType } from "../types/chart";
import {
   applyChartTheme,
   getChartCardStyle,
   getEmptyStateStyle
} from "../utils/themeUtils";
import { ChartExportButton } from "./ChartExportButton";

const { useToken } = theme;
const { Text } = Typography;

/**
 * Props every themed chart component receives at render time. The component
 * registry above is deliberately heterogeneous (`React.ElementType`), so
 * render-time injection uses this least-satisfied shape instead of `any`.
 */
type ThemedChartProps = {
   key?: React.Key;
   onReady?: (plot: Chart) => void;
   [prop: string]: unknown;
};

/**
 * Mapping of chart types to their corresponding Ant Design chart components
 */
const chartComponents: Record<ChartType, React.ElementType> = {
   line: React.lazy(() =>
      import("@ant-design/plots").then((m) => ({ default: m.Line }))
   ),
   bar: React.lazy(() =>
      import("@ant-design/plots").then((m) => ({ default: m.Bar }))
   ),
   column: React.lazy(() =>
      import("@ant-design/plots").then((m) => ({ default: m.Column }))
   ),
   area: React.lazy(() =>
      import("@ant-design/plots").then((m) => ({ default: m.Area }))
   ),
   pie: React.lazy(() =>
      import("@ant-design/plots").then((m) => ({ default: m.Pie }))
   ),
   scatter: React.lazy(() =>
      import("@ant-design/plots").then((m) => ({ default: m.Scatter }))
   ),
   dualAxes: React.lazy(() =>
      import("@ant-design/plots").then((m) => ({ default: m.DualAxes }))
   ),
   funnel: React.lazy(() =>
      import("@ant-design/plots").then((m) => ({ default: m.Funnel }))
   ),
   heatmap: React.lazy(() =>
      import("@ant-design/plots").then((m) => ({ default: m.Heatmap }))
   ),
   histogram: React.lazy(() =>
      import("@ant-design/plots").then((m) => ({ default: m.Histogram }))
   ),
   box: React.lazy(() =>
      import("@ant-design/plots").then((m) => ({ default: m.Box }))
   ),
   radar: React.lazy(() =>
      import("@ant-design/plots").then((m) => ({ default: m.Radar }))
   ),
   stock: React.lazy(() =>
      import("@ant-design/plots").then((m) => ({ default: m.Stock }))
   )
} as const;

/**
 * Props for the ChartFactory component
 */
export interface ChartFactoryProps {
   config: ChartConfig;
   loading?: boolean;
   className?: string;
   isDarkMode?: boolean;
   /** Callback when chart is ready, provides chart instance for export */
   onReady?: (chartInstance: Chart) => void;
   /** Whether to show export button */
   showExport?: boolean;
   /** Additional elements to show in the chart header */
   extra?: React.ReactNode;
}

/**
 * Error component for validation failures using Ant Design components
 */
const ValidationErrors: React.FC<{ errors: Array<{ message?: string }> }> = ({
   errors
}) => (
   <Alert
      type="error"
      showIcon
      title="Chart Configuration Errors"
      description={
         <ul style={{ margin: 0, paddingLeft: "20px" }}>
            {errors.map((error, idx) => (
               <li key={idx}>
                  <Text type="danger">
                     {error.message || "Unknown validation error"}
                  </Text>
               </li>
            ))}
         </ul>
      }
   />
);

/**
 * ChartFactory component that creates chart components dynamically with schema validation
 * This is now a React component to properly handle theme hooks
 */
export const ChartFactory: React.FC<ChartFactoryProps> = ({
   config,
   loading = false,
   className,
   isDarkMode = false,
   onReady,
   showExport = true,
   extra
}) => {
   const { token } = useToken();
   const [chartInstance, setChartInstance] = useState<Chart | null>(null);

   // Schema validation - validate before rendering
   const validation = validateChart(config, config.chartType);
   if (!validation.valid) {
      return <ValidationErrors errors={validation.errors} />;
   }

   // Convert Kontext config to Ant Design Charts format
   let convertedConfig: Record<string, unknown>;
   try {
      convertedConfig = convertChartConfig(config) as Record<string, unknown>;
   } catch (error) {
      return (
         <ValidationErrors
            errors={[
               {
                  message: `Configuration conversion error: ${
                     error instanceof Error ? error.message : "Unknown error"
                  }`
               }
            ]}
         />
      );
   }

   // Loading state
   if (loading) {
      return (
         <div className={className}>
            <div style={{ textAlign: "center", padding: "20px" }}>
               <Spin size="large" />
               <div style={{ marginTop: 8 }}>Loading chart...</div>
            </div>
         </div>
      );
   }

   // Empty data state
   if (
      !convertedConfig.data ||
      !Array.isArray(convertedConfig.data) ||
      convertedConfig.data.length === 0
   ) {
      return (
         <Card className={className} style={getChartCardStyle(token)}>
            <Empty
               description="No data available for chart"
               image={Empty.PRESENTED_IMAGE_SIMPLE}
               style={getEmptyStateStyle(token)}
            />
         </Card>
      );
   }

   // Apply theme-aware configuration
   const themedConfig = applyChartTheme(
      convertedConfig,
      token,
      isDarkMode,
      config.chartType as ChartType
   );

   // Handle chart ready callback
   const handleChartReady = (plot: Chart) => {
      setChartInstance(plot);
      onReady?.(plot);
   };

   // Add unique key to force React to re-render when chart type or color palette changes
   // This prevents DOM element reuse issues when switching between chart types or color palettes
   const chartKey = `chart-${config.chartType}-${
      config.colorPalette || "default"
   }-${isDarkMode ? "dark" : "light"}`;

   // Get the chart component for the current chart type
   const ChartComponent =
      chartComponents[config.chartType as keyof typeof chartComponents];

   // Handle unsupported chart types
   if (!ChartComponent) {
      return (
         <ValidationErrors
            errors={[
               {
                  message: `Unsupported chart type: ${config.chartType}`
               }
            ]}
         />
      );
   }

   // Handle loading state
   if (loading) {
      return (
         <div
            className={className}
            style={{ textAlign: "center", padding: "20px" }}
         >
            <Spin size="large" />
         </div>
      );
   }

   // Render the chart directly
   return (
      <Card
         className={className}
         style={{ ...getChartCardStyle(token), position: "relative" }}
         styles={{
            body: {
               padding: 0
            }
         }}
      >
         {(showExport || extra) && (
            <div
               style={{
                  position: "absolute",
                  top: token.paddingSM,
                  right: token.paddingSM,
                  zIndex: 10
               }}
            >
               <Space size="small">
                  {extra}
                  {showExport && (
                     <ChartExportButton
                        chartInstance={chartInstance}
                        data={convertedConfig.data as TabularData}
                        filename={config.title?.toString() || "chart"}
                        size="small"
                        showText={false}
                     />
                  )}
               </Space>
            </div>
         )}
         <div style={{ padding: token.paddingLG }}>
            <React.Suspense
               fallback={
                  <div
                     style={{
                        height: 300,
                        display: "flex",
                        justifyContent: "center",
                        alignItems: "center"
                     }}
                  >
                     <Spin />
                  </div>
               }
            >
               {React.createElement(
                  ChartComponent as React.ComponentType<ThemedChartProps>,
                  {
                     key: chartKey,
                     ...themedConfig,
                     onReady: handleChartReady
                  }
               )}
            </React.Suspense>
         </div>
      </Card>
   );
};
