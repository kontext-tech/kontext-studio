import type { ChartDocument, DataTable } from "@kontext-tech/schema";
import { resolveChartQueryResponse } from "../chartQueryResponse";

const baseTable: DataTable = {
   columns: [
      {
         name: "category",
         type: "string"
      }
   ],
   rows: [["A"]],
   rowCount: 1
};

const baseChart: ChartDocument = {
   name: "Sales",
   config: {
      chartType: "column",
      xField: "category",
      yField: "value"
   },
   dataRef: {
      dataId: "00000000-0000-0000-0000-000000000001"
   }
};

describe("resolveChartQueryResponse", () => {
   it("uses inline data when present", () => {
      const inlineTable: DataTable = {
         columns: [
            {
               name: "category",
               type: "string"
            }
         ],
         rows: [["Inline"]],
         rowCount: 1
      };

      const response = resolveChartQueryResponse(
         {
            ...baseChart,
            inlineData: {
               title: "Inline data",
               table: inlineTable
            }
         },
         baseTable
      );

      expect(response).toEqual({
         success: true,
         result: inlineTable
      });
   });

   it("falls back to the loaded remote table when inline data is absent", () => {
      const response = resolveChartQueryResponse(baseChart, baseTable);

      expect(response).toEqual({
         success: true,
         result: baseTable
      });
   });

   it("returns null when no table data is available", () => {
      expect(resolveChartQueryResponse(baseChart)).toBeNull();
   });
});
