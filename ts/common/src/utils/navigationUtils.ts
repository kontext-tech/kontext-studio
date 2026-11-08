import { getPlatformPageUrl } from "./envUtils";

/**
 * Creates a full URL for a public platform page.
 *
 * Local builds point `PUBLIC_KONTEXT_URL` at the dev server, which does not
 * serve the public docs; `getPlatformPageUrl` falls back to the canonical
 * platform in that case.
 *
 * @param path - The path to append to the platform base URL
 * @returns A string with the properly formatted public URL
 */
export const getFullUrl = (path: string): string => getPlatformPageUrl(path);

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
