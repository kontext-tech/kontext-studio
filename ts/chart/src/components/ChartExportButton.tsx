import { DownloadOutlined } from "@kontext-labs/icons";
import type { Chart } from "@ant-design/plots";
import type { TabularData } from "@kontext-labs/schema";
import type { MenuProps } from "antd";
import { App, Button, Dropdown } from "antd";
import React from "react";
import {
   downloadChart,
   exportDataToCSV,
   exportDataToJSON,
   type ExportFormat
} from "../utils/chartExport";

export interface ChartExportButtonProps {
   /** Chart instance from onReady callback */
   chartInstance: Chart | null;
   /** Chart data for CSV/JSON export */
   data?: TabularData;
   /** Custom filename (without extension) */
   filename?: string;
   /** Button size */
   size?: "small" | "middle" | "large";
   /** Show button text or icon only */
   showText?: boolean;
   /** Disabled state */
   disabled?: boolean;
}

/**
 * Chart Export Button Component
 * Provides a dropdown menu with export options for charts
 *
 * @example
 * ```tsx
 * const MyChart = () => {
 *   const [chartInstance, setChartInstance] = useState<Chart | null>(null);
 *
 *   return (
 *     <>
 *       <Line
 *         {...config}
 *         onReady={(plot) => setChartInstance(plot)}
 *       />
 *       <ChartExportButton
 *         chartInstance={chartInstance}
 *         data={config.data}
 *         filename="sales-chart"
 *       />
 *     </>
 *   );
 * };
 * ```
 */
export const ChartExportButton: React.FC<ChartExportButtonProps> = ({
   chartInstance,
   data,
   filename = "chart",
   size = "middle",
   showText = true,
   disabled = false
}) => {
   const { message } = App.useApp();

   const handleExport = async (format: ExportFormat | "csv" | "json") => {
      try {
         if (format === "csv") {
            if (!data || data.length === 0) {
               message.warning("No data available to export");
               return;
            }
            exportDataToCSV(data, filename);
            message.success("Data exported to CSV");
         } else if (format === "json") {
            if (!data || data.length === 0) {
               message.warning("No data available to export");
               return;
            }
            exportDataToJSON(data, filename);
            message.success("Data exported to JSON");
         } else {
            if (!chartInstance) {
               message.error("Chart not ready for export");
               return;
            }
            await downloadChart(chartInstance, { format, filename });
            message.success(`Chart exported as ${format.toUpperCase()}`);
         }
      } catch (error) {
         console.error("Export failed:", error);
         message.error(
            `Export failed: ${
               error instanceof Error ? error.message : "Unknown error"
            }`
         );
      }
   };

   const menuItems: MenuProps["items"] = [
      {
         key: "image",
         type: "group",
         label: "Export as Image",
         children: [
            {
               key: "png",
               label: "PNG Image",
               onClick: () => handleExport("png"),
               disabled: !chartInstance
            }
         ]
      },
      {
         type: "divider"
      },
      {
         key: "data",
         type: "group",
         label: "Export Data",
         children: [
            {
               key: "csv",
               label: "CSV File",
               onClick: () => handleExport("csv"),
               disabled: !data || data.length === 0
            },
            {
               key: "json",
               label: "JSON File",
               onClick: () => handleExport("json"),
               disabled: !data || data.length === 0
            }
         ]
      }
   ];

   return (
      <Dropdown
         menu={{ items: menuItems }}
         placement="bottomRight"
         disabled={disabled}
      >
         <Button
            type="text"
            icon={<DownloadOutlined />}
            size={size}
            disabled={disabled}
         >
            {showText && "Export"}
         </Button>
      </Dropdown>
   );
};
