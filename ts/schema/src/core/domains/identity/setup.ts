/**
 * Identity Domain: Setup Models
 *
 * Zod-first schema definitions for the first-launch setup wizard
 * and platform setup status.
 */

import { z } from "zod";

// ============================================================================
// Setup Request
// ============================================================================

export const SetupRequestSchema = z
   .object({
      firstName: z
         .string()
         .min(1, "First name is required")
         .max(100, "First name must not exceed 100 characters"),
      lastName: z
         .string()
         .max(100, "Last name must not exceed 100 characters")
         .nullable()
         .optional(),
      email: z.email().min(3).max(256)
   })
   .describe("Setup Request");

export type SetupRequest = z.infer<typeof SetupRequestSchema>;

// ============================================================================
// Setup Status Response
// ============================================================================

export const SetupStatusResponseSchema = z
   .object({
      isSetupComplete: z.boolean()
   })
   .describe("Setup Status Response");

export type SetupStatusResponse = z.infer<typeof SetupStatusResponseSchema>;
