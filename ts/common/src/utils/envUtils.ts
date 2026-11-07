/**
 * Utility functions for working with environment variables
 * Supports both SSR (Astro) and client-side (browser) contexts
 */

/**
 * Unified environment accessor that works in both SSR and client contexts
 */
function getEnvVar(key: string): string | undefined {
   // Client-side: use injected window.ENV first
   if (typeof window !== "undefined" && window.ENV) {
      const envKey = key as keyof typeof window.ENV;
      const value = window.ENV[envKey];
      return typeof value === "string" ? value : value?.toString();
   }

   // Server-side: try to access process.env (Node.js)
   if (typeof process !== "undefined" && process.env) {
      return process.env[key];
   }

   return undefined;
}

/**
 * The canonical public site that hosts all non-authenticated Kontext pages
 * (docs, about, contact). Used whenever PUBLIC_KONTEXT_URL is not configured.
 */
export const DEFAULT_PLATFORM_URL = "https://kontext.tech";

/**
 * Canonical documentation site for the Kontext Studio product. Kept separate
 * from the platform URL so Help links land on product docs, not platform docs.
 */
export const DEFAULT_DOCS_URL = "https://docs.kontext.tech";

/**
 * Gets the base URL for the public Kontext site from environment variables.
 * Falls back to the canonical public site so links to public pages (docs,
 * about, contact) always resolve to a real destination.
 * @returns The base URL for the public Kontext site
 */
export const getBaseUrl = (): string => {
   return getEnvVar("PUBLIC_KONTEXT_URL") || DEFAULT_PLATFORM_URL;
};

export const getDocsUrl = (path = ""): string => {
   const base = (
      getEnvVar("PUBLIC_KONTEXT_DOCS_URL") || DEFAULT_DOCS_URL
   ).replace(/\/$/, "");
   return path ? `${base}/${path.replace(/^\//, "")}` : base;
};

const LOCAL_HOSTNAMES = new Set(["localhost", "127.0.0.1", "0.0.0.0", "::1"]);

const isLocalHostname = (hostname: string) => {
   const normalized = hostname.replace(/^\[|\]$/g, "").toLowerCase();
   return LOCAL_HOSTNAMES.has(normalized) || normalized.endsWith(".localhost");
};

/**
 * Gets a page on the public Kontext platform (about, contact, ...). In local
 * mode PUBLIC_KONTEXT_URL points at the app itself, which does not serve those
 * pages, so a local URL falls back to the canonical public site.
 */
export const getPlatformPageUrl = (path = ""): string => {
   const configured = getEnvVar("PUBLIC_KONTEXT_URL");
   let base = DEFAULT_PLATFORM_URL;

   if (configured) {
      try {
         const url = new URL(configured);
         if (!isLocalHostname(url.hostname)) {
            base = configured.replace(/\/$/, "");
         }
      } catch {
         // A malformed override should not produce a broken link.
      }
   }

   return path ? `${base}/${path.replace(/^\//, "")}` : base;
};

/**
 * Gets the API URL for the application from environment variables
 * @returns The API URL for the application
 */
export const getApiUrl = (): string => {
   return getEnvVar("PUBLIC_KONTEXT_API_URL") || "http://localhost:8101";
};

/**
 * Gets the app URL for the application from environment variables
 * @returns The app URL for the application
 */
export const getAppUrl = (): string => {
   return getEnvVar("PUBLIC_KONTEXT_APP_URL") || "/";
};

/**
 * Gets the Data API URL for the application from environment variables
 * @returns The Data API URL
 */
export const getDataApiUrl = (): string => {
   return getEnvVar("PUBLIC_KONTEXT_DATA_API_URL") || "http://localhost:8000";
};

/**
 * Gets the Kontext updates project ID from environment variables
 * @returns The project ID for Kontext updates
 */
export const getKontextUpdatesProjectId = (): string => {
   return (
      getEnvVar("PUBLIC_KONTEXT_UPDATES_PROJECT_ID") ||
      "7561fe4e-6ffd-5631-96d6-cf89fdadba83"
   );
};

/**
 * Checks if the application is running in development mode
 * @returns True if running in development mode, false otherwise
 */
export const isDevelopment = (): boolean => {
   // Check various development indicators
   const devEnv =
      getEnvVar("NODE_ENV") === "development" ||
      getEnvVar("IS_DEVELOPMENT") === "true" ||
      getEnvVar("VITE_MODE") === "development";

   // Client-side: also check window.ENV if available
   if (typeof window !== "undefined") {
      // If explicitly set in window.ENV, respect that
      if (window.ENV?.IS_DEVELOPMENT === true) {
         return true;
      }

      // Fallback: check if we are running on localhost
      if (
         window.location.hostname === "localhost" ||
         window.location.hostname === "127.0.0.1"
      ) {
         return true;
      }
   }

   return devEnv;
};

/**
 * Process-level local-mode deployment flag (injected via `window.ENV`).
 *
 * This is NOT the same truth as `SiteFeature.LOCAL_MODE` in
 * `SiteConfigResponse.features` (see `useIsLocalMode()` in
 * `@kontext-labs/site`): the env flag is known before any server round-trip,
 * so it is only valid for very early decisions that cannot wait for
 * `/config/site` — currently the local auth rehydration bootstrap in
 * `@kontext-labs/identity`. Once the site config is available, code must
 * check `SiteFeature.LOCAL_MODE` membership there instead.
 */
export const isLocalMode = (): boolean => {
   const value = getEnvVar("KONTEXT_LOCAL_MODE");
   return value === true.toString() || value === "1";
};

// API-related constants and utilities

/**
 * Gets the base API path for the application
 * @returns The base API path
 */
export const getApiBasePath = (): string => {
   return getApiUrl();
};

/**
 * The base path for API requests
 */
export const API_BASE_PATH = getApiBasePath();

/**
 * The path for CAPTCHA requests
 */
export const CAPTCHA_PATH = `${API_BASE_PATH}/captcha`;
