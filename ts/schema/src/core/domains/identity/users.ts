/**
 * Identity Domain: User Models
 *
 * Zod-first schema definitions for user management.
 */

import { z } from "zod";
import {
   RoleModelSchema,
   UserWithProjectRolesModelSchema,
   UserWithRolesModelSchema
} from "./roles.js";
import { UserDetailsModelSchema, UserNavModelSchema } from "./types.js";

// ============================================================================
// User Models
// ============================================================================

export const UserModelSchema = UserNavModelSchema.extend({
   userName: z.string().max(256),
   roles: z.array(z.lazy(() => RoleModelSchema)).default([]),
   dateRegister: z.iso.datetime({ offset: true }).nullable().optional()
}).describe("User Model - Full user information");

export type UserModel = z.infer<typeof UserModelSchema>;

export const UserDetailsWithEmailModelSchema = UserDetailsModelSchema.extend({
   email: z.string().max(256).nullable().optional(),
   preferredLanguageCode: z
      .string()
      .max(16, "Language code must not exceed 16 characters")
      .nullable()
      .optional(),
   isEnabled: z.boolean()
}).describe("User Details With Email Model");

export type UserDetailsWithEmailModel = z.infer<
   typeof UserDetailsWithEmailModelSchema
>;

// ============================================================================
// User Request Models
// ============================================================================

export const UserRegistrationRequestSchema = z
   .object({
      email: z.email().max(256),
      invitationCode: z.string().max(64),
      password: z
         .string()
         .min(6, "Password must be at least 6 characters")
         .max(100, "Password must not exceed 100 characters")
         .describe("format: password"),
      confirmPassword: z
         .string()
         .min(6, "Confirm password must be at least 6 characters")
         .describe("format: password"),
      agreeWithPrivacyPolicy: z.boolean(),
      firstName: z
         .string()
         .min(1, "First name is required")
         .max(100, "First name must not exceed 100 characters")
         .regex(
            /^[a-zA-ZÀ-ÿ][-'a-zA-ZÀ-ÿ ]{1,}$/,
            "First name must start with a letter and can only contain letters, hyphens, apostrophes and spaces"
         ),
      lastName: z
         .string()
         .max(100, "Last name must not exceed 100 characters")
         .regex(
            /^[a-zA-ZÀ-ÿ][-'a-zA-ZÀ-ÿ ]{0,}$/,
            "Last name must start with a letter and can only contain letters, hyphens, apostrophes and spaces"
         )
         .nullable()
         .optional(),
      subscribe: z.boolean(),
      preferredLanguageCode: z
         .string()
         .max(16, "Language code must not exceed 16 characters")
         .regex(
            /^[a-zA-Z]{2,3}(-[a-zA-Z]{2,8})*$/,
            "Invalid language code format"
         )
   })
   .describe("User Registration Request");

export type UserRegistrationRequest = z.infer<
   typeof UserRegistrationRequestSchema
>;

export const UpdateUserProfileRequestSchema = z
   .object({
      firstName: z
         .string()
         .min(1, "First name is required")
         .max(100, "First name must not exceed 100 characters")
         .regex(
            /^[a-zA-ZÀ-ÿ][-'a-zA-ZÀ-ÿ ]{0,}$/,
            "First name must start with a letter and can only contain letters, hyphens, apostrophes and spaces"
         ),
      lastName: z
         .string()
         .max(100, "Last name must not exceed 100 characters")
         .regex(
            /^[a-zA-ZÀ-ÿ][-'a-zA-ZÀ-ÿ ]{0,}$/,
            "Last name must start with a letter and can only contain letters, hyphens, apostrophes and spaces"
         )
         .nullable()
         .optional(),
      preferredLanguageCode: z
         .string()
         .max(16, "Language code must not exceed 16 characters")
         .regex(
            /^[a-zA-Z]{2,3}(-[a-zA-Z]{2,8})*$/,
            "Invalid language code format"
         )
         .nullable()
         .optional()
   })
   .describe("Update User Profile Request");

export type UpdateUserProfileRequest = z.infer<
   typeof UpdateUserProfileRequestSchema
>;

export const UpdateUserCredentialsRequestSchema = z
   .object({
      newEmail: z.email().max(256).nullable().optional(),
      newPassword: z
         .string()
         .min(8, "New password must be at least 8 characters")
         .max(100, "New password must not exceed 100 characters")
         .regex(
            /^(?=.*[A-Z])(?=.*[0-9])(?=.*[!@#$%^&*(),.?""{}|<>])/,
            "The password must contain at least one uppercase character, one lowercase character, one digit, and one special character."
         )
         .describe("format: password")
         .nullable()
         .optional(),
      oldPassword: z
         .string()
         .min(1, "Old password is required")
         .describe("format: password")
         .nullable()
         .optional()
   })
   .describe("Update User Credentials Request");

export type UpdateUserCredentialsRequest = z.infer<
   typeof UpdateUserCredentialsRequestSchema
>;

/**
 * C#-only ViewModel (currently not exposed in Core OpenAPI)
 * Source: backend/Kontext.Data/ViewModels/Identity/UserEditViewModel.cs
 */
export const UpdateUserRequestSchema = z
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
      email: z.email().max(256),
      isEnabled: z.boolean(),
      isDeleted: z.boolean(),
      lockoutEnabled: z.boolean(),
      lockoutEnd: z.iso.datetime({ offset: true }).nullable().optional(),
      userName: z.string().max(256),
      roles: z
         .array(z.lazy(() => RoleModelSchema))
         .nullable()
         .optional()
   })
   .describe("Update User Request");

export type UpdateUserRequest = z.infer<typeof UpdateUserRequestSchema>;

/**
 * C#-only ViewModel (currently not exposed in Core OpenAPI)
 * Source: backend/Kontext.Data/ViewModels/Identity/UserMetadata.cs
 */
export const UserMetadataSchema = z
   .object({
      email: z.email().max(256),
      firstName: z
         .string()
         .min(1, "First name is required")
         .max(100, "First name must not exceed 100 characters"),
      lastName: z
         .string()
         .max(100, "Last name must not exceed 100 characters")
         .nullable()
         .optional(),
      twoFactorEnabled: z.boolean().default(false),
      phoneNumber: z.string().nullable().optional(),
      emailConfirmed: z.boolean().default(false),
      lockoutEnabled: z.boolean().default(true),
      password: z
         .string()
         .min(1, "Password is required")
         .describe("format: password"),
      rememberMe: z.boolean().default(false),
      dateRegister: z.iso.datetime({ offset: true }).nullable().optional()
   })
   .describe("User Metadata");

export type UserMetadata = z.infer<typeof UserMetadataSchema>;

// ============================================================================
// Paginated User Lists
// ============================================================================

export const PaginatedListOfUserWithRolesModelSchema = z
   .object({
      items: z.array(z.lazy(() => UserWithRolesModelSchema)).default([]),
      totalCount: z.number().int(),
      pageIndex: z.number().int(),
      pageSize: z.number().int(),
      totalPages: z.number().int().optional()
   })
   .describe("Paginated List Of User With Roles Model");

export type PaginatedListOfUserWithRolesModel = z.infer<
   typeof PaginatedListOfUserWithRolesModelSchema
>;

export const PaginatedListOfUserWithProjectRolesModelSchema = z
   .object({
      items: z.array(z.lazy(() => UserWithProjectRolesModelSchema)).default([]),
      totalCount: z.number().int(),
      pageIndex: z.number().int(),
      pageSize: z.number().int(),
      totalPages: z.number().int().optional()
   })
   .describe("Paginated List Of User With Project Roles Model");

export type PaginatedListOfUserWithProjectRolesModel = z.infer<
   typeof PaginatedListOfUserWithProjectRolesModelSchema
>;
