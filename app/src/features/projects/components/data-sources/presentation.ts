import { formatTimeAgo } from "@kontext-tech/common";
import type { CatalogConnection } from "@kontext-tech/schema";

export interface ReadinessStatus {
   color: string;
   label: string;
}

/**
 * Map a catalog connection's readiness to a tag.
 *
 * Some surfaces distinguish a queued sync from an in-progress one; others
 * collapse both into "Syncing". Pass `distinguishQueued` to opt into the
 * former.
 */
export const getReadinessStatusFor = (
   reason: string | null | undefined,
   isReady: boolean | undefined,
   { distinguishQueued = false }: { distinguishQueued?: boolean } = {}
): ReadinessStatus => {
   if (isReady) {
      return { color: "green", label: "Ready" };
   }

   switch (reason) {
      case "disabled":
         return { color: "default", label: "Disabled" };
      case "queued":
         return distinguishQueued
            ? { color: "gold", label: "Queued" }
            : { color: "processing", label: "Syncing" };
      case "running":
         return { color: "processing", label: "Syncing" };
      case "failed":
         return { color: "red", label: "Failed" };
      default:
         return { color: "default", label: "Not synced" };
   }
};

export const getReadinessStatus = (
   connection: CatalogConnection
): ReadinessStatus =>
   getReadinessStatusFor(connection.readinessReason, connection.isQueryReady);

export const getReadinessDescription = (connection: CatalogConnection) => {
   if (connection.isQueryReady) {
      return "Ready to use in chat.";
   }

   switch (connection.readinessReason) {
      case "disabled":
         return "This data source is disabled.";
      case "queued":
         return "Initial sync is queued.";
      case "running":
         return "Metadata sync is in progress.";
      case "failed":
         return connection.lastSyncError || "The latest sync failed.";
      default:
         return "Run a sync before using this data source in chat.";
   }
};

const getConnectionLocationLabel = (connection: CatalogConnection) => {
   const { config } = connection;

   if (config.databasePath) {
      return config.databasePath;
   }

   const hostLabel = config.host || "Host not configured";
   const targetLabel = config.databaseName || config.serviceName;
   return targetLabel ? `${hostLabel} / ${targetLabel}` : hostLabel;
};

export const getConnectionDetailsLine = (connection: CatalogConnection) => {
   const parts = [getConnectionLocationLabel(connection)];

   if (connection.lastValidatedAt) {
      parts.push(`Validated ${formatTimeAgo(connection.lastValidatedAt)}`);
   }

   if (connection.lastSyncedAt) {
      parts.push(`Synced ${formatTimeAgo(connection.lastSyncedAt)}`);
   }

   return parts.join(" • ");
};

export const getLatestWarning = (connection: CatalogConnection) => {
   if (connection.lastSyncStatus === "failed") {
      return connection.lastSyncError || null;
   }

   if ((connection.healthStatus || "").toLowerCase() === "failed") {
      return connection.validationError || null;
   }

   return null;
};
