import { format, formatDistanceToNow } from "date-fns";

/**
 * Date formatting utilities for Kontext
 * Centralized date utilities to be used across all packages
 */

/**
 * Formats a date as a "time ago" string (e.g., "5 minutes ago", "2 days ago")
 * Using UTC time to ensure consistent calculation regardless of user's timezone
 * @param date The date to format, can be a Date object or string
 * @returns A string representing time elapsed since the provided date
 */
export function formatTimeAgo(date: string | Date | undefined): string {
   if (!date) return "";
   return formatDistanceToNow(new Date(date), { addSuffix: true });
}

/**
 * Formats a date as YYYY-MM-DD HH:mm:ss
 * @param date The date to format, can be a Date object or string
 * @returns A string representing the date in YYYY-MM-DD HH:mm:ss format
 */
export function formatFullDateTime(date: string | Date | undefined): string {
   if (!date) return "";
   return format(new Date(date), "yyyy-MM-dd HH:mm:ss");
}

/**
 * Formats a date as a locale string (used as a fallback)
 * @param date The date to format, can be a Date object or string
 * @returns A string representing the formatted date
 */
export function formatDate(date: string | Date | undefined): string {
   if (!date) return "";
   return new Date(date).toLocaleString();
}
