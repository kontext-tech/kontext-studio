import { convertChartConfig } from "../converters";
// Mock types since we might not have access to full schema types in test environment easily
// or just use any to bypass strict checks for this unit test

describe("convertChartConfig", () => {
   it("adds scale formatter to line chart", () => {
      const config: Record<string, unknown> = {
         chartType: "line",
         title: "Test Chart",
         xField: "date",
         yField: "value",
         data: [{ date: "2023-01-01", value: 1000 }]
      };
      const converted = convertChartConfig(config) as Record<string, unknown>;
      expect(converted.scale).toBeDefined();
      expect(converted.scale.value).toBeDefined();
      expect(converted.scale.value.formatter).toBeDefined();
      expect(converted.scale.value.formatter(1000)).toBe("1K");
   });

   it("adds scale formatter to bar chart", () => {
      const config: Record<string, unknown> = {
         chartType: "bar",
         title: "Test Chart",
         xField: "category",
         yField: "sales",
         data: [{ category: "A", sales: 2500000 }]
      };
      const converted = convertChartConfig(config) as Record<string, unknown>;
      expect(converted.scale).toBeDefined();
      expect(converted.scale.sales).toBeDefined();
      expect(converted.scale.sales.formatter(2500000)).toBe("2.5M");
   });

   it("adds axis formatters to dual axes chart", () => {
      const config: Record<string, unknown> = {
         chartType: "dualAxes",
         xField: "month",
         leftYField: "txn_count",
         rightYField: "total_amount",
         numberFormat: "thousands",
         data: [{ month: "Jan", txn_count: 1000, total_amount: 1000000 }]
      };
      const converted = convertChartConfig(config) as Record<string, unknown>;
      expect(converted.scale).toBeDefined();
      expect(converted.scale.txn_count.formatter(1000)).toBe("1K");
      expect(converted.scale.total_amount.formatter(1000000)).toBe("1000K");

      expect(converted.children[0].axis.y.labelFormatter(1000)).toBe("1K");
      expect(converted.children[1].axis.y.labelFormatter(1000000)).toBe(
         "1000K"
      );
   });

   it("passes histogram bin field through converter", () => {
      const config: Record<string, unknown> = {
         chartType: "histogram",
         title: "Histogram",
         height: 400,
         binField: "value",
         data: [{ value: 10 }]
      };
      const converted = convertChartConfig(config) as Record<string, unknown>;
      expect(converted.binField).toBe("value");
   });

   it("passes box type through converter", () => {
      const config: Record<string, unknown> = {
         chartType: "box",
         title: "Box",
         height: 400,
         xField: "category",
         yField: "value",
         boxType: "boxplot",
         data: [{ category: "A", value: [1, 2, 3, 4, 5] }]
      };
      const converted = convertChartConfig(config) as Record<string, unknown>;
      expect(converted.boxType).toBe("boxplot");
   });

   it("adds scale formatter to radar chart", () => {
      const config: Record<string, unknown> = {
         chartType: "radar",
         title: "Radar",
         height: 400,
         xField: "metric",
         yField: "score",
         coordinateType: "radar",
         data: [{ metric: "A", score: 2500000 }],
         scale: {
            score: {
               domain: [0, 100]
            }
         }
      };
      const converted = convertChartConfig(config) as Record<string, unknown>;
      expect(converted.coordinateType).toBe("polar");
      expect(converted.scale).toBeDefined();
      expect(converted.scale.score).toBeDefined();
      expect(converted.scale.score.formatter(2500000)).toBe("2.5M");
      expect(converted.scale.score.domain).toEqual([0, 100]);
   });

   it("adds scale formatters to stock chart tuple fields", () => {
      const config: Record<string, unknown> = {
         chartType: "stock",
         title: "Stock",
         height: 400,
         xField: "time",
         yField: ["open", "close", "low", "high"],
         data: [
            {
               time: "2024-01-01",
               open: 1000,
               close: 2000,
               low: 500,
               high: 3000
            }
         ]
      };
      const converted = convertChartConfig(config) as Record<string, unknown>;
      expect(converted.scale.open.formatter(1000)).toBe("1K");
      expect(converted.scale.close.formatter(2000)).toBe("2K");
      expect(converted.scale.low.formatter(500)).toBe("500");
      expect(converted.scale.high.formatter(3000)).toBe("3K");
   });
});
