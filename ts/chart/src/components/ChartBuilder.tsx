import {
   AreaChartOutlined,
   BarChartOutlined,
   ChartNoAxesCombinedOutlined,
   ColumnChartOutlined,
   DotChartOutlined,
   LineChartOutlined,
   PieChartOutlined,
   StockOutlined
} from "@kontext-tech/icons";
import type { TabularData } from "@kontext-tech/schema";
import { Card, Col, Input, Row, Select, Space, Typography, theme } from "antd";
import React, { useMemo } from "react";
import {
   CHART_TYPE_ICONS,
   CHART_TYPE_NAMES,
   type ChartConfig,
   type ChartType
} from "../types";
import { ChartPreview } from "./ChartPreview";
import { ColorPaletteSelect } from "./ColorPaletteSelect";
import { NumberFormatSelect } from "./NumberFormatSelect";
import { createChartConfigComponent } from "./config";

const { Text } = Typography;
const { Option } = Select;

// Helper function to get icon component by name
const getChartIcon = (iconName: string) => {
   const iconMap = {
      LineChartOutlined: <LineChartOutlined />,
      BarChartOutlined: <BarChartOutlined />,
      ColumnChartOutlined: <ColumnChartOutlined />,
      AreaChartOutlined: <AreaChartOutlined />,
      PieChartOutlined: <PieChartOutlined />,
      DotChartOutlined: <DotChartOutlined />,
      StockOutlined: <StockOutlined />,
      ChartNoAxesCombinedOutlined: <ChartNoAxesCombinedOutlined />
   };
   return iconMap[iconName as keyof typeof iconMap] || null;
};

export interface ChartBuilderProps {
   /** The chart block data to edit */
   data: {
      chartType: ChartType;
      chartConfig: ChartConfig;
   };
   /** Direct data to use for the chart (preferred in new architecture) */
   chartData?: TabularData;
   /** Whether the builder is in preview mode (show only chart) */
   previewMode?: boolean;
   /** Whether the builder is readonly */
   readonly?: boolean;
   /** Whether to use dark mode theme */
   isDarkMode?: boolean;
   /** Custom CSS class name */
   className?: string;
   /** Optional onChange callback that overrides store updates */
   onChange?: (data: {
      chartType: ChartType;
      chartConfig: ChartConfig;
   }) => void;
}

/**
 * Professional Chart Builder Component
 *
 * A comprehensive chart building interface with:
 * - Header section for chart name and data table selection
 * - Left panel for chart-specific configuration
 * - Right panel with chart preview and configuration code tabs
 * - Preview mode for showing only the chart
 */
export const ChartBuilder: React.FC<ChartBuilderProps> = ({
   data,
   chartData,
   previewMode = false,
   readonly = false,
   isDarkMode = false,
   className,
   onChange
}) => {
   const { token } = theme.useToken();
   // Use data directly as chart configuration
   const chartConfig = useMemo(
      () =>
         ({
            ...data.chartConfig,
            data: chartData,
            chartType: data.chartType
         }) as ChartConfig,
      [data, chartData]
   ) as ChartConfig;

   // Get available columns from chart data
   const availableColumns = useMemo(() => {
      if (!chartData || chartData.length === 0) return [];
      return Object.keys(chartData[0]).map((colName) => ({
         name: colName,
         type: "string" as const
      }));
   }, [chartData]);

   // Handle chart configuration changes
   const handleChartConfigChange = (updates: Partial<ChartConfig>) => {
      if (readonly) return;

      if (onChange) {
         onChange({
            chartType: data.chartType,
            chartConfig: { ...data.chartConfig, ...updates } as ChartConfig
         });
      }
   };

   // Handle chart type change - create new config with clean defaults
   const handleChartTypeChange = (newChartType: ChartType) => {
      if (readonly) return;

      const chartDefaults: Record<string, unknown> =
         newChartType === "box"
            ? { boxType: "box" }
            : newChartType === "radar"
              ? { coordinateType: "polar" }
              : newChartType === "histogram"
                ? { binField: undefined }
                : newChartType === "stock"
                  ? { yField: undefined }
                  : {};

      // Create the updated data with the new chart type
      const newData = {
         ...data,
         chartType: newChartType,
         chartConfig: {
            ...data.chartConfig,
            chartType: newChartType,
            ...chartDefaults
         }
      };

      if (onChange) {
         onChange(newData as typeof data);
      }
   };

   if (previewMode) {
      return (
         <div className={className}>
            <ChartPreview
               chartConfig={chartConfig}
               showTabs={true}
               isDarkMode={isDarkMode}
            />
         </div>
      );
   }

   return (
      <div className={className}>
         <Row gutter={[16, 12]} style={{ marginBottom: token.marginSM }}>
            <Col span={24}>
               <Input
                  value={chartConfig.title || ""}
                  onChange={(e) =>
                     handleChartConfigChange({
                        ...chartConfig,
                        title: e.target.value
                     })
                  }
                  placeholder="Enter chart name"
                  disabled={readonly}
               />
            </Col>
         </Row>
         <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} lg={12}>
               <Space
                  orientation="vertical"
                  style={{ width: "100%" }}
                  size="large"
               >
                  <Card size="small">
                     <Space
                        orientation="vertical"
                        style={{ width: "100%" }}
                        size="middle"
                     >
                        <div>
                           <Text strong>Chart Type</Text>
                           <br />
                           <Select
                              value={data.chartType}
                              onChange={handleChartTypeChange}
                              style={{ width: "100%", marginTop: 8 }}
                              disabled={readonly}
                           >
                              {Object.entries(CHART_TYPE_NAMES).map(
                                 ([key, name]) => (
                                    <Option key={key} value={key}>
                                       <Space>
                                          {getChartIcon(
                                             CHART_TYPE_ICONS[key as ChartType]
                                          )}
                                          {name}
                                       </Space>
                                    </Option>
                                 )
                              )}
                           </Select>
                        </div>

                        <ColorPaletteSelect
                           value={chartConfig.colorPalette}
                           onChange={(colorPalette) =>
                              handleChartConfigChange({
                                 ...chartConfig,
                                 colorPalette
                              })
                           }
                           disabled={readonly}
                        />

                        <NumberFormatSelect
                           value={chartConfig.numberFormat}
                           onChange={(numberFormat) =>
                              handleChartConfigChange({
                                 ...chartConfig,
                                 numberFormat
                              })
                           }
                           disabled={readonly}
                        />

                        {createChartConfigComponent(
                           chartConfig,
                           availableColumns,
                           handleChartConfigChange,
                           readonly
                        )}
                     </Space>
                  </Card>
               </Space>
            </Col>

            <Col xs={24} lg={12}>
               <ChartPreview
                  chartConfig={chartConfig}
                  showTabs={true}
                  isDarkMode={isDarkMode}
               />
            </Col>
         </Row>
      </div>
   );
};
