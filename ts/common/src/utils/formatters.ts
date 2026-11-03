/**
 * Formats a file size in bytes into a human-readable string (KB, MB, GB, etc.).
 * @param bytes - The file size in bytes.
 * @param decimals - The number of decimal places to display.
 * @returns A formatted string representing the file size.
 */
export const formatFileSize = (bytes: number, decimals = 2): string => {
   if (bytes === 0) return "0 Bytes";

   const k = 1024;
   const dm = decimals < 0 ? 0 : decimals;
   const sizes = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"];

   const i = Math.floor(Math.log(bytes) / Math.log(k));

   return (
      parseFloat((bytes / Math.pow(k, i)).toFixed(dm)).toString() +
      " " +
      sizes[i]
   );
};

/**
 * Formats a duration (milliseconds) into a human-readable string.
 * - If `short` is true: compact format used in tables (e.g., "15ms", "1.23s").
 * - Otherwise: verbose format like "1d 2h 3m", "4h 5m 6s", "3m 20s", or "45s".
 *
 * If `ms` is undefined or null, returns "N/A". For zero returns "0s".
 */
export function formatDuration(ms?: number | null, short = false): string {
   if (ms === undefined || ms === null) return "N/A";
   if (ms === 0) return "0s";

   if (short) {
      if (ms < 1000) return `${ms}ms`;
      return `${(ms / 1000).toFixed(2)}s`;
   }

   const seconds = Math.floor(ms / 1000);
   const minutes = Math.floor(seconds / 60);
   const hours = Math.floor(minutes / 60);
   const days = Math.floor(hours / 24);

   if (days > 0) {
      return `${days}d ${hours % 24}h ${minutes % 60}m`;
   } else if (hours > 0) {
      return `${hours}h ${minutes % 60}m ${seconds % 60}s`;
   } else if (minutes > 0) {
      return `${minutes}m ${seconds % 60}s`;
   } else {
      return `${seconds}s`;
   }
}
