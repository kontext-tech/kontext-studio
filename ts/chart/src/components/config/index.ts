// Chart configuration component mapping
import type {
   AreaChartConfig as AreaChartConfigType,
   BarChartConfig as BarChartConfigType,
   BoxChartConfig as BoxChartConfigType,
   ColumnChartConfig as ColumnChartConfigType,
   DualAxesChartConfig as DualAxesChartConfigType,
   FunnelChartConfig as FunnelChartConfigType,
   HeatMapConfig as HeatMapConfigType,
   HistogramChartConfig as HistogramChartConfigType,
   LineChartConfig as LineChartConfigType,
   PieChartConfig as PieChartConfigType,
   RadarChartConfig as RadarChartConfigType,
   ScatterChartConfig as ScatterChartConfigType,
   StockChartConfig as StockChartConfigType
} from "@kontext-labs/schema";
import React from "react";
import type { ChartConfig, Field } from "../../types";
import { AreaChartConfig } from "./AreaChartConfig";
import { BarChartConfig } from "./BarChartConfig";
import { BoxChartConfig } from "./BoxChartConfig";
import { ColumnChartConfig } from "./ColumnChartConfig";
import { DualAxesChartConfig } from "./DualAxesChartConfig";
import { FunnelChartConfig } from "./FunnelChartConfig";
import { HeatMapChartConfig } from "./HeatMapChartConfig";
import { HistogramChartConfig } from "./HistogramChartConfig";
import { LineChartConfig } from "./LineChartConfig";
import { PieChartConfig } from "./PieChartConfig";
import { RadarChartConfig } from "./RadarChartConfig";
import { ScatterChartConfig } from "./ScatterChartConfig";
import { StockChartConfig } from "./StockChartConfig";

/**
 * Type-safe factory function to create chart configuration components
 * @param config - Chart configuration containing the chart type
 * @param availableColumns - Available data fields
 * @param onChange - Configuration change handler
 * @param readonly - Whether the component is readonly
 * @returns JSX element for the appropriate chart configuration component
 */
export function createChartConfigComponent(
   config: ChartConfig,
   availableColumns: Field[],
   onChange: (updates: Partial<ChartConfig>) => void,
   readonly?: boolean
): React.ReactNode {
   // Use switch statement for type-safe component selection
   switch (config.chartType) {
      case "line":
         return React.createElement(LineChartConfig, {
            config: config as LineChartConfigType,
            availableColumns,
            onChange: onChange as (
               updates: Partial<LineChartConfigType>
            ) => void,
            readonly
         });
      case "area":
         return React.createElement(AreaChartConfig, {
            config: config as AreaChartConfigType,
            availableColumns,
            onChange: onChange as (
               updates: Partial<AreaChartConfigType>
            ) => void,
            readonly
         });
      case "bar":
         return React.createElement(BarChartConfig, {
            config: config as BarChartConfigType,
            availableColumns,
            onChange: onChange as (
               updates: Partial<BarChartConfigType>
            ) => void,
            readonly
         });
      case "box":
         return React.createElement(BoxChartConfig, {
            config: config as BoxChartConfigType,
            availableColumns,
            onChange: onChange as (
               updates: Partial<BoxChartConfigType>
            ) => void,
            readonly
         });
      case "column":
         return React.createElement(ColumnChartConfig, {
            config: config as ColumnChartConfigType,
            availableColumns,
            onChange: onChange as (
               updates: Partial<ColumnChartConfigType>
            ) => void,
            readonly
         });
      case "pie":
         return React.createElement(PieChartConfig, {
            config: config as PieChartConfigType,
            availableColumns,
            onChange: onChange as (
               updates: Partial<PieChartConfigType>
            ) => void,
            readonly
         });
      case "scatter":
         return React.createElement(ScatterChartConfig, {
            config: config as ScatterChartConfigType,
            availableColumns,
            onChange: onChange as (
               updates: Partial<ScatterChartConfigType>
            ) => void,
            readonly
         });
      case "dualAxes":
         return React.createElement(DualAxesChartConfig, {
            config: config as DualAxesChartConfigType,
            availableColumns,
            onChange: onChange as (
               updates: Partial<DualAxesChartConfigType>
            ) => void,
            readonly
         });
      case "funnel":
         return React.createElement(FunnelChartConfig, {
            config: config as FunnelChartConfigType,
            availableColumns,
            onChange: onChange as (
               updates: Partial<FunnelChartConfigType>
            ) => void,
            readonly
         });
      case "heatmap":
         return React.createElement(HeatMapChartConfig, {
            config: config as HeatMapConfigType,
            availableColumns,
            onChange: onChange as (updates: Partial<HeatMapConfigType>) => void,
            readonly
         });
      case "histogram":
         return React.createElement(HistogramChartConfig, {
            config: config as HistogramChartConfigType,
            availableColumns,
            onChange: onChange as (
               updates: Partial<HistogramChartConfigType>
            ) => void,
            readonly
         });
      case "radar":
         return React.createElement(RadarChartConfig, {
            config: config as RadarChartConfigType,
            availableColumns,
            onChange: onChange as (
               updates: Partial<RadarChartConfigType>
            ) => void,
            readonly
         });
      case "stock":
         return React.createElement(StockChartConfig, {
            config: config as StockChartConfigType,
            availableColumns,
            onChange: onChange as (
               updates: Partial<StockChartConfigType>
            ) => void,
            readonly
         });
      default:
         // This should never happen with proper TypeScript types
         console.error(
            `Unsupported chart type: ${(config as ChartConfig).chartType}`
         );
         return null;
   }
}
