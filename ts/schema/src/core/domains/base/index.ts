import { z } from "zod";
export * from "./types.js";

/**
 * Core Domain: Base / Shared Models
 *
 * These are C# ViewModels that may not be part of the current Core OpenAPI surface,
 * but are included for eventual replacement of C# models with generated Kontext.Schemas.
 */

// Source: backend/Kontext.Data/ViewModels/IBaseViewModel.cs
export const BaseModelSchema = z
   .object({
      id: z.guid()
   })
   .describe("Base Model");

export type BaseModel = z.infer<typeof BaseModelSchema>;

export const SortBySchema = z
   .enum([
      "Default",
      "Latest",
      "Creation",
      "Views",
      "Likes",
      "Modified",
      "Name",
      "Title",
      "Rating",
      "Popularity"
   ])
   .describe("Sorting order for various data services");

export const SortBy = SortBySchema.enum;
export type SortBy = z.infer<typeof SortBySchema>;

/**
 * Core Domain: Config
 *
 * Source: backend/Kontext.Data/ViewModels/Config/ConfigViewModel.cs
 */
export const ConfigModelSchema = z
   .object({
      siteName: z.string(),
      appUrl: z.string(),
      siteUrl: z.string(),
      cookieUrl: z.string(),
      privacyUrl: z.string(),
      termsUrl: z.string(),
      contactUrl: z.string()
   })
   .describe("Config Model");

export type ConfigModel = z.infer<typeof ConfigModelSchema>;

/**
 * Core Domain: Site Config Response
 *
 * Lightweight site configuration returned by the /config endpoint.
 * Contains feature flags and display settings — distinct from the
 * full ConfigModel which carries internal service URLs.
 */
export const SiteConfigResponseSchema = z
   .object({
      siteName: z.string(),
      defaultProjectCode: z.string().nullable().optional(),
      authEnabled: z.boolean(),
      registrationEnabled: z.boolean(),
      features: z.array(z.string()).default([]),
      /**
       * When set, the frontend should redirect unauthenticated users to this URL
       * for first-time setup. Null means setup is already complete or not applicable.
       * The server controls this URL so it can change the setup path without frontend
       * rebuild (e.g. cloud onboarding flows vs. local CLI setup wizard).
       */
      setupUrl: z.string().nullable().optional()
   })
   .describe("Site Config Response");

export type SiteConfigResponse = z.infer<typeof SiteConfigResponseSchema>;

/**
 * Server-advertised site-level feature flags.
 *
 * The server returns the subset it supports in `SiteConfigResponse.features`.
 * Frontend code checks membership rather than branching on `isLocalMode()`,
 * so new capabilities can be toggled server-side without a frontend redeploy.
 *
 * Usage:
 *   siteConfig.features.includes(SiteFeature.NOTIFICATIONS)
 */
export const SiteFeature = {
   /** Real-time notification bell + inbox. */
   NOTIFICATIONS: "notifications",
   /** Subscription management (billing / notification groups). */
   SUBSCRIPTIONS: "subscriptions",
   /** Password change and 2FA management in Account settings. */
   USER_AUTH_MANAGEMENT: "user-auth-management",
   /** Require CAPTCHA on login, register, and forgot-password forms. */
   CAPTCHA: "captcha",
   /** Registration requires a valid invitation code (Step 1 of the wizard). */
   INVITATION_REQUIRED: "invitation-required",
   /** App is running in local (self-hosted / offline) mode. */
   LOCAL_MODE: "local-mode",
   /** Executable AI model connection management is available. */
   MODEL_CONNECTIONS: "model-connections",
   /** Managed Python runtime metadata page is available. */
   PYTHON_ENVIRONMENT: "python-environment"
} as const;

export type SiteFeature = (typeof SiteFeature)[keyof typeof SiteFeature];

export const PythonEnvironmentPackageSchema = z
   .object({
      name: z.string(),
      version: z.string(),
      spec: z.string()
   })
   .describe("Managed Python environment package");

export type PythonEnvironmentPackage = z.infer<
   typeof PythonEnvironmentPackageSchema
>;

export const PythonPackageSourceSchema = z.enum(["configured", "installed"]);

export type PythonPackageSource = z.infer<typeof PythonPackageSourceSchema>;
export const PythonPackageSource = PythonPackageSourceSchema.enum;

export const PythonEnvironmentInfoSchema = z
   .object({
      available: z.boolean(),
      initialized: z.boolean(),
      displayLabel: z.string(),
      backend: z.string(),
      runtimeProfile: z.string(),
      pythonVersion: z.string(),
      packageSource: z.lazy(() => PythonPackageSourceSchema),
      packages: z.array(PythonEnvironmentPackageSchema).default([])
   })
   .describe("Managed Python environment metadata");

export type PythonEnvironmentInfo = z.infer<typeof PythonEnvironmentInfoSchema>;
