// Formats a number with commas as thousand separators (e.g., 1,234,567)
export function formatNumberWithCommas(num?: number): string {
   if (num === undefined) return "0";
   return num.toLocaleString();
}
