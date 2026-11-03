import type { NumberFormat } from "@kontext-labs/schema";

/**
 * Format number to specified notation
 * @param value number to format
 * @param format formatting style
 * @param digits number of decimal places (default: 1)
 * @returns formatted string
 */
export function formatNumber(
   value: number | string,
   format: NumberFormat = "short",
   digits = 1
): string {
   if (value === null || value === undefined || value === "") return "";
   const num = Number(value);
   if (isNaN(num)) return String(value);

   if (format === "none") return num.toLocaleString();

   const rx = /\.0+$|(\.[0-9]*[1-9])0+$/;

   if (format === "thousands")
      return (num / 1e3).toFixed(digits).replace(rx, "$1") + "K";
   if (format === "millions")
      return (num / 1e6).toFixed(digits).replace(rx, "$1") + "M";
   if (format === "billions")
      return (num / 1e9).toFixed(digits).replace(rx, "$1") + "B";

   // Default: "short" auto-detect
   if (num === 0) return "0";

   const lookup = [
      { value: 1, symbol: "" },
      { value: 1e3, symbol: "K" },
      { value: 1e6, symbol: "M" },
      { value: 1e9, symbol: "B" },
      { value: 1e12, symbol: "T" }
   ];

   const item = lookup
      .slice()
      .reverse()
      .find((item) => Math.abs(num) >= item.value);

   return item
      ? (num / item.value).toFixed(digits).replace(rx, "$1") + item.symbol
      : num.toFixed(digits).replace(rx, "$1");
}
