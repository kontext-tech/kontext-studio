/**
 * Identity Domain: Shared Types and Enums
 */

import { z } from "zod";

// ============================================================================
// Enums
// ============================================================================

export const UserTypeSchema = z
   .enum(["User", "ServiceAccount"])
   .describe("User Type enum");

export type UserType = z.infer<typeof UserTypeSchema>;

// Export enum constants directly for runtime usage
export const UserType = UserTypeSchema.enum;

// ============================================================================
// Base User Models
// ============================================================================

export const UserDetailsModelSchema = z
   .object({
      id: z.guid(),
      firstName: z
         .string()
         .max(100, "First name must not exceed 100 characters"),
      lastName: z
         .string()
         .max(100, "Last name must not exceed 100 characters")
         .nullable()
         .optional()
   })
   .describe("User Details Model - Base user information");

export type UserDetailsModel = z.infer<typeof UserDetailsModelSchema>;

export const UserNavModelSchema = UserDetailsModelSchema.extend({
   email: z.string().max(256).nullable().optional(),
   isEnabled: z.boolean().optional(),
   isDeleted: z.boolean().optional(),
   lockoutEnabled: z.boolean().optional(),
   lockoutEnd: z.iso.datetime({ offset: true }).nullable().optional(),
   isLockedOut: z.boolean().optional(),
   preferredLanguageCode: z
      .string()
      .max(16, "Language code must not exceed 16 characters")
      .nullable()
      .optional(),
   emailConfirmed: z.boolean().optional(),
   userType: z.lazy(() => UserTypeSchema).optional()
}).describe("User Nav Model - User navigation/list view");

export type UserNavModel = z.infer<typeof UserNavModelSchema>;
