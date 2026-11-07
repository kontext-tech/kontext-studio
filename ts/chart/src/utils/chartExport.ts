/**
 * Chart export utilities for downloading charts in various formats
 * Leverages @ant-design/plots (G2Plot) built-in export capabilities
 */

import type { Chart } from "@ant-design/plots";
import type { TabularData } from "@kontext-tech/schema";

export type ExportFormat = "png";

export interface ExportOptions {
   /** Output format for the exported chart */
   format?: ExportFormat;
   /** Filename for the downloaded file (without extension) */
   filename?: string;
   /** Background color for the exported image (default: white) */
   backgroundColor?: string;
}

/**
 * Downloads a chart as an image file
 * Works with any @ant-design/plots chart component that has been rendered
 *
 * @param chartInstance - Chart instance from onReady callback
 * @param options - Export options
 *
 * @example
 * ```tsx
 * const [chartRef, setChartRef] = useState<Chart | null>(null);
 *
 * <Line {...config} onReady={(plot) => setChartRef(plot)} />
 * <Button onClick={() => downloadChart(chartRef, { format: 'png', filename: 'my-chart' })}>
 *   Export PNG
 * </Button>
 * ```
 */
export const downloadChart = async (
   chartInstance: Chart | null,
   options: ExportOptions = {}
): Promise<void> => {
   if (!chartInstance) {
      throw new Error("Chart instance is required for export");
   }

   const {
      format = "png",
      filename = `chart-${Date.now()}`,
      backgroundColor = "#ffffff"
   } = options;

   const extension = format;
   const fullFilename = filename.endsWith(`.${extension}`)
      ? filename
      : `${filename}.${extension}`;
   const mimeType = `image/${format}`;

   try {
      // @ant-design/plots charts expose a downloadImage method for PNG
      if (
         format === "png" &&
         typeof chartInstance.downloadImage === "function"
      ) {
         await chartInstance.downloadImage(fullFilename, mimeType);
         return;
      }

      // Fallback: Use Canvas toDataURL for PNG
      const canvas = chartInstance.chart?.getCanvas?.();
      const canvasElement = canvas?.get("el") as HTMLCanvasElement;

      if (!canvasElement) {
         throw new Error("Unable to access chart canvas for export");
      }

      // Create a temporary canvas with background color
      const tempCanvas = document.createElement("canvas");
      tempCanvas.width = canvasElement.width;
      tempCanvas.height = canvasElement.height;
      const ctx = tempCanvas.getContext("2d");

      if (!ctx) {
         throw new Error("Unable to create canvas context");
      }

      // Fill background
      ctx.fillStyle = backgroundColor;
      ctx.fillRect(0, 0, tempCanvas.width, tempCanvas.height);

      // Draw chart on top
      ctx.drawImage(canvasElement, 0, 0);

      // Convert to data URL
      const dataUrl = tempCanvas.toDataURL(mimeType, 0.95);

      // Trigger download
      triggerDownload(dataUrl, fullFilename);
   } catch (error) {
      console.error("Chart export failed:", error);
      throw Object.assign(
         new Error(
            `Failed to export chart: ${
               error instanceof Error ? error.message : "Unknown error"
            }`
         ),
         { cause: error }
      );
   }
};

/**
 * Triggers a browser download for a data URL or blob URL
 */
const triggerDownload = (url: string, filename: string): void => {
   const link = document.createElement("a");
   link.href = url;
   link.download = filename;
   document.body.appendChild(link);
   link.click();
   document.body.removeChild(link);
};

/**
 * Exports chart data to CSV format
 * Useful for exporting the raw data behind the chart
 *
 * @param data - Chart data array
 * @param filename - Output filename (without extension)
 *
 * @example
 * ```tsx
 * const data = [
 *   { category: 'A', value: 10 },
 *   { category: 'B', value: 20 }
 * ];
 *
 * <Button onClick={() => exportDataToCSV(data, 'chart-data')}>
 *   Export Data
 * </Button>
 * ```
 */
export const exportDataToCSV = (
   data: TabularData,
   filename: string = `chart-data-${Date.now()}`
): void => {
   if (!data || data.length === 0) {
      throw new Error("No data to export");
   }

   try {
      // Get headers from first row
      const headers = Object.keys(data[0]);

      // Create CSV content
      const csvRows = [
         headers.join(","), // Header row
         ...data.map((row) =>
            headers
               .map((header) => {
                  const value = row[header];
                  // Escape quotes and wrap in quotes if contains comma/quote/newline
                  const stringValue = String(value ?? "");
                  if (
                     stringValue.includes(",") ||
                     stringValue.includes('"') ||
                     stringValue.includes("\n")
                  ) {
                     return `"${stringValue.replace(/"/g, '""')}"`;
                  }
                  return stringValue;
               })
               .join(",")
         )
      ];

      const csvContent = csvRows.join("\n");
      const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);

      triggerDownload(url, `${filename}.csv`);
      URL.revokeObjectURL(url);
   } catch (error) {
      console.error("CSV export failed:", error);
      throw Object.assign(
         new Error(
            `Failed to export data to CSV: ${
               error instanceof Error ? error.message : "Unknown error"
            }`
         ),
         { cause: error }
      );
   }
};

/**
 * Exports chart data to JSON format
 *
 * @param data - Chart data array
 * @param filename - Output filename (without extension)
 */
export const exportDataToJSON = (
   data: TabularData,
   filename: string = `chart-data-${Date.now()}`
): void => {
   if (!data || data.length === 0) {
      throw new Error("No data to export");
   }

   try {
      const jsonContent = JSON.stringify(data, null, 2);
      const blob = new Blob([jsonContent], {
         type: "application/json;charset=utf-8;"
      });
      const url = URL.createObjectURL(blob);

      triggerDownload(url, `${filename}.json`);
      URL.revokeObjectURL(url);
   } catch (error) {
      console.error("JSON export failed:", error);
      throw Object.assign(
         new Error(
            `Failed to export data to JSON: ${
               error instanceof Error ? error.message : "Unknown error"
            }`
         ),
         { cause: error }
      );
   }
};
