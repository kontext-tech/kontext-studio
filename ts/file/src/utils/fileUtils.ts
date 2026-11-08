import type { FileModel } from "@kontext-tech/schema";

type DesktopBlobBridge = {
   saveBlob?: (blob: Blob, filename: string) => Promise<unknown>;
};

declare global {
   interface Window {
      __KONTEXT_DESKTOP__?: DesktopBlobBridge;
   }
}

/**
 * Checks if a resource is an image based on its content type
 */
export const isImageResource = (resource: FileModel): boolean => {
   const imageTypes = [
      "image/jpeg",
      "image/png",
      "image/gif",
      "image/webp",
      "image/svg+xml"
   ];
   return imageTypes.includes(resource.contentType?.toLowerCase() || "");
};

/**
 * Creates a download link for a blob and triggers the download.
 *
 * WKWebView does not honor `<a download>` for `blob:` URLs, so the desktop
 * shell injects a native save bridge. The browser path remains unchanged.
 */
export const downloadBlob = (blob: Blob, filename: string): void => {
   const desktopBridge = window.__KONTEXT_DESKTOP__;
   if (desktopBridge?.saveBlob) {
      desktopBridge.saveBlob(blob, filename).catch(() => undefined);
      return;
   }

   const url = window.URL.createObjectURL(blob);
   const link = document.createElement("a");
   link.href = url;
   link.download = filename;
   document.body.appendChild(link);
   link.click();
   document.body.removeChild(link);
   window.URL.revokeObjectURL(url);
};

/**
 * Generates a unique filename by appending a timestamp to avoid naming conflicts
 * @param filename The original filename (e.g., "image.png")
 * @param index Optional index for batch operations to ensure uniqueness across multiple files
 * @returns A unique filename with timestamp (e.g., "image-1725123456789.png" or "image-1725123456789-0.png")
 */
export const generateUniqueFilename = (
   filename: string,
   index?: number
): string => {
   const lastDotIndex = filename.lastIndexOf(".");
   const baseName =
      lastDotIndex > 0 ? filename.substring(0, lastDotIndex) : filename;
   const extension = lastDotIndex > 0 ? filename.substring(lastDotIndex) : "";

   const timestamp = Date.now();
   const indexSuffix = index !== undefined ? `-${index}` : "";

   return `${baseName}-${timestamp}${indexSuffix}${extension}`;
};

/**
 * Extracts resource ID from various URL formats
 */
export const extractResourceId = {
   /**
    * Extracts resource ID from API URLs (e.g., "/api/resource/guid-here" or "/resource/guid-here")
    * @param url The URL to extract from
    * @returns The resource ID or null if not found
    */
   fromApiUrl: (url: string): string | null => {
      const match = url.match(/\/resource\/([a-fA-F0-9-]+)(?:\?|$)/);
      return match ? match[1] : null;
   },

   /**
    * Extracts resource ID from resource:// protocol URLs (e.g., "resource://guid-here")
    * @param url The URL to extract from
    * @returns The resource ID or null if not found
    */
   fromResourceUrl: (url: string): string | null => {
      const match = url.match(/^resource:\/\/([^/\s]+)/);
      return match ? match[1] : null;
   },

   /**
    * Extracts resource ID from HTML img tags with resource:// URLs
    * @param imgTag The HTML img tag
    * @returns The resource ID or null if not found
    */
   fromImgTag: (imgTag: string): string | null => {
      const match = imgTag.match(
         /<img[^>]+src=["']resource:\/\/([^"']+)["'][^>]*>/i
      );
      return match ? match[1] : null;
   },

   /**
    * Extracts resource ID from any supported URL format
    * @param input The URL, img tag, or comment to extract from
    * @returns The resource ID or null if not found
    */
   fromAny: (input: string): string | null => {
      // Try API URL first
      let resourceId = extractResourceId.fromApiUrl(input);
      if (resourceId) return resourceId;

      // Try resource:// URL
      resourceId = extractResourceId.fromResourceUrl(input);
      if (resourceId) return resourceId;

      // Try HTML img tag
      resourceId = extractResourceId.fromImgTag(input);
      if (resourceId) return resourceId;

      return null;
   }
};
