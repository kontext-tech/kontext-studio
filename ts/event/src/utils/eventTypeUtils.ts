import { EventType } from "@kontext-labs/schema";

export interface EventTypeConfig {
   displayName: string;
   color: string;
   category:
      "create" | "update" | "delete" | "view" | "auth" | "security" | "other";
   priority: number; // For sorting in lists
}

/**
 * Comprehensive configuration for all event types
 * Provides consistent display names, colors, categories, and summaries
 */
const EVENT_TYPE_CONFIG: Record<EventType, EventTypeConfig> = {
   [EventType.Other]: {
      displayName: "Other Event",
      color: "default",
      category: "other",
      priority: 100
   },

   // Site Events
   [EventType.CreateProject]: {
      displayName: "Project Created",
      color: "green",
      category: "create",
      priority: 5
   },
   [EventType.ModifyProject]: {
      displayName: "Project Modified",
      color: "orange",
      category: "update",
      priority: 6
   },
   [EventType.ViewProject]: {
      displayName: "Project Viewed",
      color: "cyan",
      category: "view",
      priority: 7
   },
   [EventType.ViewPage]: {
      displayName: "Page Viewed",
      color: "cyan",
      category: "view",
      priority: 48
   },

   [EventType.CreateCatalogEntity]: {
      displayName: "Catalog Entity Created",
      color: "green",
      category: "create",
      priority: 16
   },
   [EventType.UpdateCatalogEntity]: {
      displayName: "Catalog Entity Updated",
      color: "orange",
      category: "update",
      priority: 26
   },
   [EventType.DeleteCatalogEntity]: {
      displayName: "Catalog Entity Deleted",
      color: "red",
      category: "delete",
      priority: 36
   },

   // Authentication Events
   [EventType.Login]: {
      displayName: "User Login",
      color: "blue",
      category: "auth",
      priority: 60
   },
   [EventType.EditProfile]: {
      displayName: "Profile Edited",
      color: "blue",
      category: "update",
      priority: 61
   },
   [EventType.ChangePassword]: {
      displayName: "Password Changed",
      color: "blue",
      category: "security",
      priority: 62
   },
   [EventType.Enable2FA]: {
      displayName: "Two-Factor Authentication Enabled",
      color: "green",
      category: "security",
      priority: 63
   },
   [EventType.Disable2FA]: {
      displayName: "Two-Factor Authentication Disabled",
      color: "orange",
      category: "security",
      priority: 64
   },
   [EventType.EnableUser]: {
      displayName: "User Enabled",
      color: "green",
      category: "auth",
      priority: 65
   },
   [EventType.DisableUser]: {
      displayName: "User Disabled",
      color: "red",
      category: "auth",
      priority: 66
   },
   [EventType.Register]: {
      displayName: "User Registration",
      color: "green",
      category: "auth",
      priority: 67
   },
   [EventType.ConfirmEmail]: {
      displayName: "Email Confirmed",
      color: "blue",
      category: "auth",
      priority: 68
   },
   [EventType.SessionRefresh]: {
      displayName: "Session Refreshed",
      color: "blue",
      category: "auth",
      priority: 69
   },

   // Subscription Events
   [EventType.SubscribeToGroup]: {
      displayName: "Subscribed to Group",
      color: "green",
      category: "create",
      priority: 80
   },
   [EventType.UnsubscribeFromGroup]: {
      displayName: "Unsubscribed from Group",
      color: "orange",
      category: "delete",
      priority: 81
   },

   // Service Account Events
   [EventType.CreateServiceAccount]: {
      displayName: "Service Account Created",
      color: "green",
      category: "create",
      priority: 70
   },
   [EventType.EnableServiceAccount]: {
      displayName: "Service Account Enabled",
      color: "green",
      category: "auth",
      priority: 71
   },
   [EventType.DisableServiceAccount]: {
      displayName: "Service Account Disabled",
      color: "red",
      category: "auth",
      priority: 72
   },
   [EventType.AuthenticateServiceAccount]: {
      displayName: "Service Account Authenticated",
      color: "blue",
      category: "auth",
      priority: 73
   },
   [EventType.CreateServiceAccountKey]: {
      displayName: "Service Account Key Created",
      color: "green",
      category: "create",
      priority: 74
   },
   [EventType.EnableServiceAccountKey]: {
      displayName: "Service Account Key Enabled",
      color: "green",
      category: "auth",
      priority: 75
   },
   [EventType.DisableServiceAccountKey]: {
      displayName: "Service Account Key Disabled",
      color: "red",
      category: "auth",
      priority: 76
   },
   [EventType.DeleteServiceAccountKey]: {
      displayName: "Service Account Key Deleted",
      color: "red",
      category: "delete",
      priority: 77
   },

   // File Events
   [EventType.CreateFile]: {
      displayName: "File Created",
      color: "green",
      category: "create",
      priority: 12
   },
   [EventType.CreateFiles]: {
      displayName: "Files Created (Batch)",
      color: "green",
      category: "create",
      priority: 13
   },
   [EventType.DeleteFile]: {
      displayName: "File Deleted",
      color: "red",
      category: "delete",
      priority: 14
   },
   [EventType.UpdateFileSchema]: {
      displayName: "File Schema Updated",
      color: "blue",
      category: "update",
      priority: 15
   },

   // Campaign Events
   [EventType.RequestCampaignEmailDelivery]: {
      displayName: "Campaign Email Delivery Requested",
      color: "green",
      category: "create",
      priority: 20
   },

   // Failed Event Processing
   [EventType.ProcessFailedEvent]: {
      displayName: "Failed Event Processing",
      color: "volcano",
      category: "other",
      priority: 99
   }
};

/**
 * Get the configuration for an event type
 */
export const getEventTypeConfig = (
   type: EventType | undefined
): EventTypeConfig => {
   if (!type || !(type in EVENT_TYPE_CONFIG)) {
      return EVENT_TYPE_CONFIG[EventType.Other];
   }
   return EVENT_TYPE_CONFIG[type];
};

/**
 * Get the category of an event type
 */
export const getEventCategory = (type: EventType | undefined): string => {
   return getEventTypeConfig(type).category;
};

/**
 * Get a display name for an event type
 */
export const getEventTypeName = (type: EventType | undefined): string => {
   return getEventTypeConfig(type).displayName;
};

/**
 * Get all event types sorted by priority and category
 */
export const getSortedEventTypes = (): EventType[] => {
   return Object.keys(EVENT_TYPE_CONFIG)
      .map((key) => key as EventType)
      .sort((a, b) => {
         const configA = EVENT_TYPE_CONFIG[a];
         const configB = EVENT_TYPE_CONFIG[b];

         // Sort by category first, then by priority
         if (configA.category !== configB.category) {
            const categoryOrder = [
               "create",
               "update",
               "delete",
               "view",
               "auth",
               "security",
               "other"
            ];
            return (
               categoryOrder.indexOf(configA.category) -
               categoryOrder.indexOf(configB.category)
            );
         }

         return configA.priority - configB.priority;
      });
};

/**
 * Get event types grouped by category
 */
export const getEventTypesByCategory = (): Record<string, EventType[]> => {
   const groups: Record<string, EventType[]> = {};

   getSortedEventTypes().forEach((type) => {
      const category = getEventCategory(type);
      if (!groups[category]) {
         groups[category] = [];
      }
      groups[category].push(type);
   });

   return groups;
};
