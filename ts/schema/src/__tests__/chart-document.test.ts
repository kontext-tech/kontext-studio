/**
 * Tests for chart document schemas
 * Tests the Zod schemas for .chart files in the data lake
 */

import { ChartDocumentSchema, type ChartDocument } from "../charts/document";
import {
   DataRefSchema,
   DataTableSchema,
   InlineDataMetadataSchema,
   InlineDataSchema,
   type DataRef
} from "../core/data";

describe("Chart Document Schemas", () => {
   describe("DataRefSchema", () => {
      it("should validate with dataId (data table reference)", () => {
         const ref: DataRef = {
            dataId: "550e8400-e29b-41d4-a716-446655440000"
         };

         const result = DataRefSchema.safeParse(ref);
         expect(result.success).toBe(true);
      });

      it("should validate with dataId (data lake reference)", () => {
         const ref: DataRef = {
            dataId: "550e8400-e29b-41d4-a716-446655440001"
         };

         const result = DataRefSchema.safeParse(ref);
         expect(result.success).toBe(true);
      });

      it("should validate without dataId for external references", () => {
         const ref: DataRef = {
            connectionId: "warehouse-prod",
            tableName: "analytics.sales_summary"
         };

         const result = DataRefSchema.safeParse(ref);
         expect(result.success).toBe(true);
      });

      it("should validate with connectionId for catalog-scoped context", () => {
         const ref: DataRef = {
            dataId: "550e8400-e29b-41d4-a716-446655440001",
            connectionId: "550e8400-e29b-41d4-a716-446655440002"
         };

         const result = DataRefSchema.safeParse(ref);
         expect(result.success).toBe(true);
      });
   });

   describe("DataTableSchema (Embedded Data)", () => {
      it("should validate embedded data in columnar format", () => {
         const table = {
            columns: [
               { name: "id", type: "int" },
               { name: "name", type: "string" }
            ],
            rows: [
               [1, "A"],
               [2, "B"]
            ],
            rowCount: 2
         };

         const result = DataTableSchema.safeParse(table);
         expect(result.success).toBe(true);
      });
   });

   describe("InlineData provenance metadata", () => {
      it("should validate inline data without metadata", () => {
         const result = InlineDataSchema.safeParse({
            title: "Result",
            table: { columns: [], rows: [[1]], rowCount: 1 }
         });

         expect(result.success).toBe(true);
      });

      it("should validate inline data with provenance metadata", () => {
         const result = InlineDataSchema.safeParse({
            title: "Result",
            table: { columns: [], rows: [[1]], rowCount: 1 },
            metadata: {
               notebookId: "550e8400-e29b-41d4-a716-446655440020",
               querySessionId: "550e8400-e29b-41d4-a716-446655440021",
               chatSessionId: "550e8400-e29b-41d4-a716-446655440022",
               sql: "SELECT 1",
               createdAt: new Date().toISOString()
            }
         });

         expect(result.success).toBe(true);
      });

      it("should strip unknown provenance fields", () => {
         const result = InlineDataMetadataSchema.safeParse({
            sql: "SELECT 1",
            unknownField: "nope"
         });

         expect(result.success).toBe(true);
         if (result.success) {
            expect(result.data).toEqual({ sql: "SELECT 1" });
         }
      });
   });

   describe("ChartDocumentSchema", () => {
      it("should validate a complete chart document with embedded data", () => {
         const doc = {
            name: "Sales Chart",
            config: {
               chartType: "line" as const,
               title: "Sales Over Time",
               height: 400,
               xField: "month",
               yField: "sales"
            },
            inlineData: {
               title: "Embedded Data",
               table: {
                  columns: [
                     { name: "month", type: "string" },
                     { name: "sales", type: "int" }
                  ],
                  rows: [
                     ["Jan", 1000],
                     ["Feb", 1200]
                  ],
                  rowCount: 2
               }
            }
         };

         const result = ChartDocumentSchema.safeParse(doc);
         expect(result.success).toBe(true);
      });

      it("should validate a chart document with data lake reference", () => {
         const doc = {
            name: "Sales Chart",
            config: {
               chartType: "bar" as const,
               title: "Sales by Region",
               height: 400,
               xField: "region",
               yField: "sales"
            },
            dataRef: {
               dataId: "550e8400-e29b-41d4-a716-446655440001",
               connectionId: "550e8400-e29b-41d4-a716-446655440002"
            }
         };

         const result = ChartDocumentSchema.safeParse(doc);
         expect(result.success).toBe(true);
      });

      it("should validate chart document with optional data table", () => {
         const doc = {
            name: "Empty Chart",
            config: {
               chartType: "column" as const,
               title: "Empty Chart",
               height: 400,
               xField: "x",
               yField: "y"
            }
         };

         const result = ChartDocumentSchema.safeParse(doc);
         expect(result.success).toBe(true);
      });

      it("should validate chart document with metadata", () => {
         const doc: ChartDocument = {
            name: "Detailed Chart",
            config: {
               chartType: "area" as const,
               title: "Chart with Metadata",
               height: 400,
               xField: "date",
               yField: "value"
            },
            metadata: {
               description: "A detailed chart showing trends",
               tags: ["trend", "sales"],
               author: "John Doe",
               createdAt: new Date().toISOString(),
               modifiedAt: new Date().toISOString(),
               version: "1.0.0"
            }
         };

         const result = ChartDocumentSchema.safeParse(doc);
         expect(result.success).toBe(true);
      });

      it("should validate chart document with generation provenance metadata", () => {
         const doc: ChartDocument = {
            name: "Provenance Chart",
            config: {
               chartType: "line" as const,
               title: "Generated Chart",
               height: 400,
               xField: "month",
               yField: "sales"
            },
            metadata: {
               createdAt: new Date().toISOString(),
               modifiedAt: new Date().toISOString(),
               notebookId: "550e8400-e29b-41d4-a716-446655440010",
               querySessionId: "550e8400-e29b-41d4-a716-446655440011",
               chatSessionId: "550e8400-e29b-41d4-a716-446655440012"
            }
         };

         const result = ChartDocumentSchema.safeParse(doc);
         expect(result.success).toBe(true);
      });

      it("should reject invalid provenance ids in chart metadata", () => {
         const doc = {
            name: "Bad Provenance Chart",
            config: {
               chartType: "line" as const,
               title: "Bad",
               height: 400,
               xField: "month",
               yField: "sales"
            },
            metadata: {
               createdAt: new Date().toISOString(),
               modifiedAt: new Date().toISOString(),
               chatSessionId: "not-a-guid"
            }
         };

         const result = ChartDocumentSchema.safeParse(doc);
         expect(result.success).toBe(false);
      });

      it("should require chart name", () => {
         const doc = {
            config: {
               chartType: "line" as const,
               title: "Test",
               height: 400,
               xField: "x",
               yField: "y"
            }
         };

         const result = ChartDocumentSchema.safeParse(doc);
         expect(result.success).toBe(false);
      });

      it("should require chart config", () => {
         const doc = {
            name: "Test Chart"
         };

         const result = ChartDocumentSchema.safeParse(doc);
         expect(result.success).toBe(false);
      });
   });
});
