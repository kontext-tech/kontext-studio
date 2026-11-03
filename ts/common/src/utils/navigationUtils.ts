import { getBaseUrl } from "./envUtils";

/**
 * Creates a full URL by combining the base URL from environment with a path
 * Ensures proper formatting with a single slash between base URL and path
 *
 * @param path - The path to append to the base URL
 * @returns A string with the properly formatted full URL
 */
export const getFullUrl = (path: string): string => {
   const baseUrl = getBaseUrl();
   return `${baseUrl.endsWith("/") ? baseUrl : baseUrl + "/"}${path}`;
};

/**
 * Navigates to a URL using browser navigation.
 * This works universally for both React routes and external URLs (like Astro pages).
 *
 * @param url - The URL to navigate to
 */
export const navigateToUrl = (url: string): void => {
   // Use window.location.replace to avoid React Router interference
   // and ensure proper navigation to absolute URLs
   window.location.replace(url);
};
