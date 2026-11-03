import type { CatalogConnection } from "@kontext-labs/schema";
import { useEffect } from "react";

const SYNCING_STATUSES = new Set(["queued", "running"]);
const SYNC_POLL_INTERVAL_MS = 3000;

/**
 * Polls a refresh callback while any catalog connection is still syncing.
 * Used by the catalog management and new-chat screens so the sync-status
 * polling behavior stays consistent.
 */
export function useCatalogSyncPolling(
   connections: CatalogConnection[],
   onPoll: () => void | Promise<void>
): void {
   useEffect(() => {
      if (
         !connections.some((connection) =>
            SYNCING_STATUSES.has(connection.lastSyncStatus || "")
         )
      ) {
         return;
      }

      const intervalId = window.setInterval(() => {
         void onPoll();
      }, SYNC_POLL_INTERVAL_MS);

      return () => window.clearInterval(intervalId);
   }, [connections, onPoll]);
}
