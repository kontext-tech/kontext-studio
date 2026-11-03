/**
 * Tests for chart schemas in @kontext-labs/schema
 * Tests the Zod schemas and their validation capabilities
 */

import {
   CHART_SCHEMAS,
   ChartConfigSchema,
   getAllChartTypes,
   getChartSchema,
   hasChartSchema,
   type ChartConfig,
   type ChartType
} from "../charts";

describe("Chart Schemas", () => {
   const chartTypes = getAllChartTypes();

   // Test each chart type with valid configurations
   const validConfigs: Record<ChartType, Partial<ChartConfig>> = {
      line: {
         chartType: "line" as const,
         title: "Line Chart",
         height: 400,
         xField: "x",
         yField: "y"
      },
      area: {
         chartType: "area" as const,
         title: "Area Chart",
         height: 400,
         xField: "x",
         yField: "y"
      },
      bar: {
         chartType: "bar" as const,
         title: "Bar Chart",
         height: 400,
         xField: "value",
         yField: "category"
      },
      column: {
         chartType: "column" as const,
         title: "Column Chart",
         height: 400,
         xField: "category",
         yField: "value"
      },
      pie: {
         chartType: "pie" as const,
         title: "Pie Chart",
         height: 400,
         angleField: "value",
         colorField: "category"
      },
      scatter: {
         chartType: "scatter" as const,
         title: "Scatter Chart",
         height: 400,
         xField: "x",
         yField: "y"
      },
      dualAxes: {
         chartType: "dualAxes" as const,
         title: "Dual Axes Chart",
         height: 400,
         xField: "x",
         leftYField: "y1",
         leftChartType: "line",
         rightYField: "y2",
         rightChartType: "line"
      },
      funnel: {
         chartType: "funnel" as const,
         title: "Funnel Chart",
         height: 400,
         xField: "stage",
         yField: "value"
      },
      heatmap: {
         chartType: "heatmap" as const,
         title: "Heat Map",
         height: 400,
         xField: "x",
         yField: "y",
         colorField: "value"
      },
      histogram: {
         chartType: "histogram" as const,
         title: "Histogram",
         height: 400,
         binField: "value"
      },
      box: {
         chartType: "box" as const,
         title: "Box Chart",
         height: 400,
         xField: "category",
         yField: "value"
      },
      radar: {
         chartType: "radar" as const,
         title: "Radar Chart",
         height: 400,
         xField: "metric",
         yField: "score"
      },
      stock: {
         chartType: "stock" as const,
         title: "Stock Chart",
         height: 400,
         xField: "time",
         yField: ["open", "close", "low", "high"]
      }
   };

   describe("Schema Registry", () => {
      it("should have all expected chart types", () => {
         const expectedTypes: ChartType[] = [
            "line",
            "area",
            "bar",
            "column",
            "pie",
            "scatter",
            "dualAxes",
            "funnel",
            "heatmap",
            "histogram",
            "box",
            "radar",
            "stock"
         ];

         expectedTypes.forEach((type) => {
            expect(chartTypes).toContain(type);
         });
      });

      it("should have schema for each chart type", () => {
         chartTypes.forEach((type) => {
            expect(hasChartSchema(type)).toBe(true);
            expect(getChartSchema(type)).toBeDefined();
         });
      });

      it("should have CHART_SCHEMAS object with all types", () => {
         chartTypes.forEach((type) => {
            expect(CHART_SCHEMAS[type]).toBeDefined();
         });
      });
   });

   describe("Schema Validation", () => {
      chartTypes.forEach((chartType) => {
         it(`should validate ${chartType} chart configuration`, () => {
            const config = validConfigs[chartType];
            const schema = getChartSchema(chartType);

            const result = schema.safeParse(config);

            if (!result.success) {
               console.error(
                  `Validation failed for ${chartType}:`,
                  result.error.issues
               );
            }

            expect(result.success).toBe(true);
         });
      });

      it("should validate with discriminated union schema", () => {
         const lineConfig = validConfigs.line;
         const result = ChartConfigSchema.safeParse(lineConfig);

         if (!result.success) {
            console.error(
               "Discriminated union validation failed:",
               result.error.issues
            );
         }

         expect(result.success).toBe(true);
      });

      it("should reject invalid chart type", () => {
         const invalidConfig = {
            chartType: "invalidType" as unknown as ChartType,
            title: "Invalid Chart",
            height: 400
         };

         const result = ChartConfigSchema.safeParse(invalidConfig);
         expect(result.success).toBe(false);
      });

      it("should reject missing required fields", () => {
         const incompleteConfig = {
            chartType: "line" as const
            // missing title and height
         };

         const result = ChartConfigSchema.safeParse(incompleteConfig);
         expect(result.success).toBe(false);
      });

      it("should reject invalid field types", () => {
         const invalidConfig = {
            chartType: "line" as const,
            title: 123 as unknown as string, // should be string
            height: "400" as unknown as number, // should be number
            xField: "x",
            yField: "y"
         };

         const result = ChartConfigSchema.safeParse(invalidConfig);
         expect(result.success).toBe(false);
      });
   });

   describe("Schema Properties", () => {
      it("should have required properties by validating sample configs", () => {
         chartTypes.forEach((chartType) => {
            const config = validConfigs[chartType];
            const schema = getChartSchema(chartType);

            // Test that required properties are indeed required by removing them
            const { title: _title, ...configWithoutTitle } = config as Record<
               string,
               unknown
            >;
            const resultWithoutTitle = schema.safeParse(configWithoutTitle);
            expect(resultWithoutTitle.success).toBe(false);

            const { height: _height, ...configWithoutHeight } =
               config as Record<string, unknown>;
            const resultWithoutHeight = schema.safeParse(configWithoutHeight);
            expect(resultWithoutHeight.success).toBe(false);
         });
      });

      it("should validate chart-specific required fields", () => {
         // Test line chart requires xField and yField
         const lineConfigWithoutX = { ...validConfigs.line } as Record<
            string,
            unknown
         >;
         delete lineConfigWithoutX.xField;
         const lineResult =
            getChartSchema("line").safeParse(lineConfigWithoutX);
         expect(lineResult.success).toBe(false);

         // Test pie chart requires angleField and colorField
         const pieConfigWithoutAngle = { ...validConfigs.pie } as Record<
            string,
            unknown
         >;
         delete pieConfigWithoutAngle.angleField;
         const pieResult = getChartSchema("pie").safeParse(
            pieConfigWithoutAngle
         );
         expect(pieResult.success).toBe(false);

         // Test heat map colorField is optional for backward compatibility
         const heatmapConfigWithoutColor = {
            ...validConfigs.heatmap
         } as Record<string, unknown>;
         delete heatmapConfigWithoutColor.colorField;
         const heatmapResult = getChartSchema("heatmap").safeParse(
            heatmapConfigWithoutColor
         );
         expect(heatmapResult.success).toBe(true);

         const histogramConfigWithoutBin = {
            ...validConfigs.histogram
         } as Record<string, unknown>;
         delete histogramConfigWithoutBin.binField;
         const histogramResult = getChartSchema("histogram").safeParse(
            histogramConfigWithoutBin
         );
         expect(histogramResult.success).toBe(false);

         const boxConfigWithoutX = { ...validConfigs.box } as Record<
            string,
            unknown
         >;
         delete boxConfigWithoutX.xField;
         expect(
            getChartSchema("box").safeParse(boxConfigWithoutX).success
         ).toBe(false);

         const boxConfigWithoutY = { ...validConfigs.box } as Record<
            string,
            unknown
         >;
         delete boxConfigWithoutY.yField;
         expect(
            getChartSchema("box").safeParse(boxConfigWithoutY).success
         ).toBe(false);

         const radarConfigWithoutX = { ...validConfigs.radar } as Record<
            string,
            unknown
         >;
         delete radarConfigWithoutX.xField;
         expect(
            getChartSchema("radar").safeParse(radarConfigWithoutX).success
         ).toBe(false);

         const radarConfigWithoutY = { ...validConfigs.radar } as Record<
            string,
            unknown
         >;
         delete radarConfigWithoutY.yField;
         expect(
            getChartSchema("radar").safeParse(radarConfigWithoutY).success
         ).toBe(false);

         const stockConfigWithoutY = { ...validConfigs.stock } as Record<
            string,
            unknown
         >;
         delete stockConfigWithoutY.yField;
         expect(
            getChartSchema("stock").safeParse(stockConfigWithoutY).success
         ).toBe(false);

         const stockConfigWithShortTuple = {
            ...validConfigs.stock,
            yField: ["open", "close", "low"]
         };
         expect(
            getChartSchema("stock").safeParse(stockConfigWithShortTuple).success
         ).toBe(false);
      });

      it("should reject invalid chart-specific enum values", () => {
         const invalidBoxType = {
            ...validConfigs.box,
            boxType: "invalid"
         };
         expect(getChartSchema("box").safeParse(invalidBoxType).success).toBe(
            false
         );

         const invalidRadarCoordinateType = {
            ...validConfigs.radar,
            coordinateType: "invalid"
         };
         expect(
            getChartSchema("radar").safeParse(invalidRadarCoordinateType)
               .success
         ).toBe(false);
      });
   });
});
