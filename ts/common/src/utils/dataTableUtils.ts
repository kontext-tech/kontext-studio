import type {
   ChartSpec,
   DataColumn,
   DataTable,
   TabularData,
   TabularRow
} from "@kontext-labs/schema";

/**
 * Data transformation utilities for converting query results to various formats
 */

/**
 * Options for converting DataTable to rows
 */
export interface DataTableConversionOptions {
   /** Add row index as _rowIndex property (useful for table keys) */
   addRowIndex?: boolean;
   /** Validate that specific columns exist */
   requiredColumns?: string[];
   /** Filter out rows with null values in required columns */
   filterNullValues?: boolean;
   /** Custom row transformer function */
   rowTransformer?: (row: TabularRow, index: number) => TabularRow | null;
}

/**
 * Result of DataTable conversion
 */
export interface DataTableConversionResult {
   /** Successfully transformed data */
   data: TabularData;
   /** Available column names */
   columns: string[];
   /** Whether transformation was successful */
   success: boolean;
   /** Error message if transformation failed */
   errorMessage?: string;
   /** Original row count before any filtering */
   originalRowCount: number;
   /** Final row count after transformation and filtering */
   finalRowCount: number;
}

/**
 * Converts DataTable rows from array-of-arrays to array-of-objects format
 *
 * @param queryResult - The DataTable to convert
 * @param options - Conversion options
 * @returns Conversion result with data and metadata
 */
export function convertDataTableToRows(
   queryResult: DataTable,
   options: DataTableConversionOptions = {}
): DataTableConversionResult {
   const {
      addRowIndex = false,
      requiredColumns = [],
      filterNullValues = false,
      rowTransformer
   } = options;

   // Validate basic structure
   if (!queryResult.columns || queryResult.columns.length === 0) {
      return {
         data: [],
         columns: [],
         success: false,
         errorMessage: "Data table has no columns",
         originalRowCount: 0,
         finalRowCount: 0
      };
   }

   if (!queryResult.rows) {
      return {
         data: [],
         columns: queryResult.columns.map((col: DataColumn) => col.name),
         success: false,
         errorMessage: "Data table has no rows",
         originalRowCount: 0,
         finalRowCount: 0
      };
   }

   const columnNames = queryResult.columns.map((col: DataColumn) => col.name);

   // Validate required columns
   for (const requiredCol of requiredColumns) {
      if (!columnNames.includes(requiredCol)) {
         return {
            data: [],
            columns: columnNames,
            success: false,
            errorMessage: `Required column '${requiredCol}' not found. Available columns: ${columnNames.join(
               ", "
            )}`,
            originalRowCount: 0,
            finalRowCount: 0
         };
      }
   }

   try {
      // Query result rows are now always array-of-arrays format
      const rowsArray = queryResult.rows as unknown[][];

      const originalRowCount = rowsArray.length;

      if (originalRowCount === 0) {
         return {
            data: [],
            columns: columnNames,
            success: true,
            errorMessage: undefined,
            originalRowCount: 0,
            finalRowCount: 0
         };
      }

      // Transform array-of-arrays to array-of-objects
      const transformedData = rowsArray
         .map((rowArray: unknown[], rowIndex: number) => {
            // Validate that row is an array
            if (!Array.isArray(rowArray)) {
               console.warn(
                  `[QueryResultTransformer] Row ${rowIndex} is not an array:`,
                  rowArray
               );
               return null;
            }

            // Create object from array values using column names
            const rowObject: TabularRow = {};
            columnNames.forEach((columnName: string, columnIndex: number) => {
               rowObject[columnName] = rowArray[columnIndex];
            });

            // Add row index if requested
            if (addRowIndex) {
               rowObject._rowIndex = rowIndex;
            }

            // Filter out rows with null values in required columns if requested
            if (filterNullValues) {
               for (const requiredCol of requiredColumns) {
                  const value = rowObject[requiredCol];
                  if (value === null || value === undefined) {
                     return null;
                  }
               }
            }

            // Apply custom row transformer if provided
            if (rowTransformer) {
               return rowTransformer(rowObject, rowIndex);
            }

            return rowObject;
         })
         .filter((row): row is TabularRow => row !== null);

      return {
         data: transformedData,
         columns: columnNames,
         success: true,
         errorMessage: undefined,
         originalRowCount,
         finalRowCount: transformedData.length
      };
   } catch (error) {
      return {
         data: [],
         columns: columnNames,
         success: false,
         errorMessage: `Failed to convert data table: ${error}`,
         originalRowCount: 0,
         finalRowCount: 0
      };
   }
}

export type AggregationFunction = "sum" | "avg" | "count" | "min" | "max";

export interface AggregationOptions {
   /** The dimension field(s) to group by */
   dimensionFields: string[];
   /** The metric field(s) to aggregate */
   metricFields: string[];
   /** Aggregation function to apply (default: sum) */
   aggregationFunction?: AggregationFunction;
}

export interface AggregationResult {
   data: TabularData;
   wasAggregated: boolean;
   originalRowCount: number;
   finalRowCount: number;
}

/**
 * Checks if the data needs aggregation based on the provided dimension fields.
 * Returns true if there are duplicate combinations of dimension values.
 */
export function needsAggregation(
   data: TabularData,
   dimensionFields: string[]
): boolean {
   if (!data || data.length === 0 || dimensionFields.length === 0) {
      return false;
   }

   const seen = new Set<string>();
   for (const row of data) {
      const key = dimensionFields
         .map((field) => String(row[field] ?? ""))
         .join("|");
      if (seen.has(key)) {
         return true;
      }
      seen.add(key);
   }

   return false;
}

/**
 * Aggregates data by grouping on specified dimensions
 */
export function aggregateData(
   data: TabularData,
   options: AggregationOptions
): AggregationResult {
   const {
      dimensionFields,
      metricFields,
      aggregationFunction = "sum"
   } = options;

   if (!data || data.length === 0) {
      return {
         data: [],
         wasAggregated: false,
         originalRowCount: 0,
         finalRowCount: 0
      };
   }

   if (!needsAggregation(data, dimensionFields)) {
      return {
         data,
         wasAggregated: false,
         originalRowCount: data.length,
         finalRowCount: data.length
      };
   }

   const groupMap = new Map<string, TabularRow>();
   const countMap = new Map<string, number>(); // For average calculation

   for (const row of data) {
      const groupKey = dimensionFields
         .map((field) => String(row[field] ?? ""))
         .join("|");

      if (!groupMap.has(groupKey)) {
         // Initialize group
         const newRow: TabularRow = {};
         // Copy dimension values
         for (const field of dimensionFields) {
            newRow[field] = row[field];
         }
         // Initialize metrics
         for (const metric of metricFields) {
            newRow[metric] = 0;
            // For min/max, initialize with the first value found
            if (
               aggregationFunction === "min" ||
               aggregationFunction === "max"
            ) {
               newRow[metric] = row[metric];
            }
         }
         groupMap.set(groupKey, newRow);
         countMap.set(groupKey, 0);
      }

      const groupRow = groupMap.get(groupKey)!;
      const currentCount = countMap.get(groupKey)!;
      countMap.set(groupKey, currentCount + 1);

      for (const metric of metricFields) {
         const val = Number(row[metric]);
         if (!isNaN(val)) {
            const currentVal = Number(groupRow[metric]);

            switch (aggregationFunction) {
               case "sum":
               case "avg": // Sum first, divide later
                  groupRow[metric] = currentVal + val;
                  break;
               case "count":
                  groupRow[metric] = currentCount + 1;
                  break;
               case "min":
                  groupRow[metric] = Math.min(currentVal, val);
                  break;
               case "max":
                  groupRow[metric] = Math.max(currentVal, val);
                  break;
            }
         }
      }
   }

   // Finalize averages if needed
   const aggregatedData = Array.from(groupMap.values()).map((row) => {
      if (aggregationFunction === "avg") {
         const groupKey = dimensionFields
            .map((field) => String(row[field] ?? ""))
            .join("|");
         const count = countMap.get(groupKey) || 1;

         for (const metric of metricFields) {
            row[metric] = Number(row[metric]) / count;
         }
      }
      return row;
   });

   return {
      data: aggregatedData,
      wasAggregated: true,
      originalRowCount: data.length,
      finalRowCount: aggregatedData.length
   };
}

/**
 * Reusable utility to prepare data for a ChartSpec.
 * Prioritizes embedded 'inlineData' over remote data.
 * Handles conversion from columnar DataTable to row-based records.
 *
 * @param spec - The chart specification
 * @param remoteTable - Remote data table (e.g. from useInlineDataFile)
 */
export const NUMERIC_TYPES = [
   "int64",
   "float64",
   "double",
   "number",
   "decimal",
   "integer",
   "numeric",
   "real"
];

/**
 * Auto-infers default chart fields (xField, yField) from available columns.
 */
export function inferChartFields(
   chartType: string,
   columns: { name: string; type: string }[]
): {
   xField?: string;
   yField?: string | [string, string, string, string];
   colorField?: string;
   angleField?: string;
   binField?: string;
} {
   if (!columns || columns.length === 0) return {};

   const isDateLike = (colDesc: { type: string }) =>
      ["date", "time", "timestamp", "datetime"].some((t) =>
         colDesc.type.toLowerCase().includes(t)
      );

   const isNumeric = (colDesc: { type: string }) =>
      NUMERIC_TYPES.some((t) => colDesc.type.toLowerCase().includes(t));

   const isString = (colDesc: { type: string }) =>
      colDesc.type.toLowerCase().includes("string") ||
      colDesc.type.toLowerCase().includes("varchar") ||
      colDesc.type.toLowerCase().includes("text");

   const numerics = columns.filter(isNumeric);
   const strings = columns.filter(isString);
   const dateLike = columns.filter(isDateLike);

   const firstStringCol = strings.length > 0 ? strings[0] : columns[0];
   const secondStringCol = strings.length > 1 ? strings[1] : undefined;
   const firstNumericCol =
      numerics.find((col) => col.name !== firstStringCol?.name) ||
      columns.find((col) => col.name !== firstStringCol?.name) ||
      columns[1] ||
      columns[0];
   const firstDateLikeCol = dateLike[0] || firstStringCol;

   switch (chartType) {
      case "pie":
      case "donut":
         return {
            colorField: firstStringCol?.name,
            angleField: firstNumericCol?.name || firstStringCol?.name
         };
      case "scatter":
      case "bubble":
         if (numerics.length >= 2) {
            return {
               xField: numerics[0]?.name,
               yField: numerics[1]?.name,
               colorField: firstStringCol?.name
            };
         }
         return {
            xField: firstStringCol?.name,
            yField: firstNumericCol?.name
         };
      case "histogram":
         return {
            binField: numerics[0]?.name || firstNumericCol?.name,
            colorField: firstStringCol?.name
         };
      case "box":
         return {
            xField: firstStringCol?.name,
            yField: firstNumericCol?.name,
            colorField: secondStringCol?.name
         };
      case "radar":
         return {
            xField: firstStringCol?.name,
            yField: firstNumericCol?.name,
            colorField: secondStringCol?.name
         };
      case "stock":
         return {
            xField: firstDateLikeCol?.name,
            yField:
               numerics.length >= 4
                  ? [
                       numerics[0].name,
                       numerics[1].name,
                       numerics[2].name,
                       numerics[3].name
                    ]
                  : undefined
         };
      case "line":
      case "bar":
      case "column":
      case "area":
      default:
         return {
            xField: firstStringCol?.name,
            yField: firstNumericCol?.name
         };
   }
}

export function extractChartDataRows(
   spec: ChartSpec | undefined,
   remoteTable: DataTable | undefined
): TabularData {
   if (!spec) {
      return [];
   }

   // 1. Prioritize embedded data
   if (spec.inlineData) {
      // Handle nested inline-data structure (content -> table)
      const table = spec.inlineData.table;

      if (table) {
         const result = convertDataTableToRows(table);
         return result.success ? result.data : [];
      }

      return [];
   }

   // 2. Use remote data if available
   if (remoteTable) {
      const result = convertDataTableToRows(remoteTable);
      return result.success ? result.data : [];
   }

   return [];
}
