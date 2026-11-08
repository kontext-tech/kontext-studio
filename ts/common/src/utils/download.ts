type DesktopBlobBridge = {
   saveBlob?: (blob: Blob, filename: string) => Promise<unknown>;
};

declare global {
   interface Window {
      __KONTEXT_DESKTOP__?: DesktopBlobBridge;
   }
}

/** Whether the desktop shell injected its native save bridge. */
export const hasDesktopSaveBridge = (): boolean =>
   typeof window.__KONTEXT_DESKTOP__?.saveBlob === "function";

/**
 * Downloads a blob through the desktop bridge when available.
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
