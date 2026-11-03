import type { InlineData } from "@kontext-labs/schema";

export const EXAMPLE_DATA_TABLES: Record<string, InlineData> = {
   "57883424-55e1-4763-9b64-b0b7f0daef5e": {
      title: "Sales Performance Analysis",
      table: {
         columns: [
            { name: "month", type: "varchar" },
            { name: "region", type: "varchar" },
            { name: "revenue", type: "decimal" },
            { name: "units_sold", type: "int" },
            { name: "customer_count", type: "int" },
            { name: "avg_order_value", type: "decimal" }
         ],
         rows: [
            ["Jan", "North", 125000.5, 450, 125, 277.78],
            ["Jan", "South", 98000.25, 380, 98, 257.89],
            ["Jan", "East", 118000.75, 420, 118, 281.14],
            ["Jan", "West", 134000.0, 475, 134, 282.11],
            ["Feb", "North", 142000.25, 510, 142, 278.43],
            ["Feb", "South", 112000.5, 420, 112, 266.67],
            ["Feb", "East", 135000.0, 485, 135, 278.35],
            ["Feb", "West", 145000.75, 495, 145, 292.93],
            ["Mar", "North", 158000.0, 575, 158, 274.78],
            ["Mar", "South", 128000.25, 485, 128, 263.93],
            ["Mar", "East", 151000.5, 550, 151, 274.55],
            ["Mar", "West", 162000.75, 540, 162, 300.0]
         ],
         rowCount: 12
      }
   },
   "67883424-55e1-4763-9b64-b0b7f0daef5e": {
      title: "Platform Capability Benchmark",
      table: {
         columns: [
            { name: "capability", type: "varchar" },
            { name: "product_area", type: "varchar" },
            { name: "score", type: "int" }
         ],
         rows: [
            ["Discoverability", "Workspace", 88],
            ["Governance", "Workspace", 82],
            ["Query Speed", "Workspace", 74],
            ["Collaboration", "Workspace", 91],
            ["Automation", "Workspace", 63],
            ["Observability", "Workspace", 79],
            ["Discoverability", "Notebook", 81],
            ["Governance", "Notebook", 78],
            ["Query Speed", "Notebook", 86],
            ["Collaboration", "Notebook", 89],
            ["Automation", "Notebook", 76],
            ["Observability", "Notebook", 72],
            ["Discoverability", "Agent Studio", 69],
            ["Governance", "Agent Studio", 75],
            ["Query Speed", "Agent Studio", 83],
            ["Collaboration", "Agent Studio", 71],
            ["Automation", "Agent Studio", 94],
            ["Observability", "Agent Studio", 88]
         ],
         rowCount: 18
      }
   },
   "77883424-55e1-4763-9b64-b0b7f0daef5e": {
      title: "KONT Daily OHLC Series",
      table: {
         columns: [
            { name: "trade_date", type: "date" },
            { name: "ticker", type: "varchar" },
            { name: "open_price", type: "decimal" },
            { name: "close_price", type: "decimal" },
            { name: "low_price", type: "decimal" },
            { name: "high_price", type: "decimal" },
            { name: "volume", type: "int" }
         ],
         rows: [
            ["2024-01-02", "KONT", 101.2, 104.8, 99.4, 106.1, 185000],
            ["2024-01-03", "KONT", 104.8, 103.5, 102.3, 107.0, 172000],
            ["2024-01-04", "KONT", 103.5, 108.4, 103.0, 109.7, 194500],
            ["2024-01-05", "KONT", 108.4, 107.1, 105.8, 110.2, 201300],
            ["2024-01-08", "KONT", 107.1, 111.6, 106.4, 112.5, 216800],
            ["2024-01-09", "KONT", 111.6, 109.9, 108.7, 113.1, 205400],
            ["2024-01-10", "KONT", 109.9, 114.2, 109.1, 115.0, 224700],
            ["2024-01-11", "KONT", 114.2, 116.8, 113.5, 117.4, 231600],
            ["2024-01-12", "KONT", 116.8, 115.3, 114.7, 118.2, 219900],
            ["2024-01-15", "KONT", 115.3, 118.9, 114.9, 119.6, 238100]
         ],
         rowCount: 10
      }
   }
};
