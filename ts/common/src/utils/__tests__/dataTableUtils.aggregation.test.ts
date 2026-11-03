/**
 * Tests for data aggregation utilities
 */

import type { TabularData } from "@kontext-labs/schema";
import { aggregateData, needsAggregation } from "../dataTableUtils";

describe("Data Aggregation Utilities", () => {
   describe("needsAggregation", () => {
      it("should return true when duplicates exist for dimension", () => {
         const data: TabularData = [
            { category: "A", value: 100 },
            { category: "A", value: 200 }
         ];
         expect(needsAggregation(data, ["category"])).toBe(true);
      });

      it("should return false when dimensions are unique", () => {
         const data: TabularData = [
            { category: "A", value: 100 },
            { category: "B", value: 200 }
         ];
         expect(needsAggregation(data, ["category"])).toBe(false);
      });

      it("should handle multi-dimension uniqueness", () => {
         const data: TabularData = [
            { dim1: "A", dim2: "1", val: 10 },
            { dim1: "A", dim2: "2", val: 20 }
         ];
         expect(needsAggregation(data, ["dim1", "dim2"])).toBe(false);
         expect(needsAggregation(data, ["dim1"])).toBe(true);
      });
   });

   describe("aggregateData", () => {
      it("should sum metric values by dimension", () => {
         const data: TabularData = [
            { category: "A", sales: 100 },
            { category: "A", sales: 150 },
            { category: "B", sales: 200 }
         ];

         const result = aggregateData(data, {
            dimensionFields: ["category"],
            metricFields: ["sales"],
            aggregationFunction: "sum"
         });

         expect(result.wasAggregated).toBe(true);
         expect(result.data.length).toBe(2);
         expect(result.data.find((r) => r.category === "A")?.sales).toBe(250);
         expect(result.data.find((r) => r.category === "B")?.sales).toBe(200);
      });

      it("should calculate averages correctly", () => {
         const data: TabularData = [
            { category: "A", value: 100 },
            { category: "A", value: 200 },
            { category: "B", value: 300 }
         ];

         const result = aggregateData(data, {
            dimensionFields: ["category"],
            metricFields: ["value"],
            aggregationFunction: "avg"
         });

         expect(result.data.find((r) => r.category === "A")?.value).toBe(150);
         expect(result.data.find((r) => r.category === "B")?.value).toBe(300);
      });

      it("should handle multiple metrics", () => {
         const data: TabularData = [
            { cat: "A", v1: 10, v2: 100 },
            { cat: "A", v1: 20, v2: 200 }
         ];

         const result = aggregateData(data, {
            dimensionFields: ["cat"],
            metricFields: ["v1", "v2"],
            aggregationFunction: "sum"
         });

         const row = result.data[0];
         expect(row.v1).toBe(30);
         expect(row.v2).toBe(300);
      });

      it("should not aggregate if not needed", () => {
         const data: TabularData = [
            { cat: "A", val: 10 },
            { cat: "B", val: 20 }
         ];

         const result = aggregateData(data, {
            dimensionFields: ["cat"],
            metricFields: ["val"]
         });

         expect(result.wasAggregated).toBe(false);
         expect(result.data).toBe(data); // Should return original reference
      });
   });
});
