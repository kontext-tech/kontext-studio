/**
 * Identity Domain: Service Account Models
 *
 * Zod-first schema definitions for service account management.
 */

import { z } from "zod";
import { UserNavModelSchema } from "./types.js";

// ============================================================================
// Service Account Models
// ============================================================================

export const ServiceAccountModelSchema = UserNavModelSchema.extend({
   activeKeyCount: z.number().int(),
   totalKeyCount: z.number().int(),
   lastKeyUsed: z.iso.datetime({ offset: true }).nullable().optional()
}).describe("Service Account Model");

export type ServiceAccountModel = z.infer<typeof ServiceAccountModelSchema>;

export const ServiceAccountKeyModelSchema = z
   .object({
      id: z.guid(),
      userId: z.guid(),
      projectId: z.guid().nullable().optional(),
      keyName: z.string().nullable().optional(),
      dateCreated: z.iso.datetime({ offset: true }),
      dateExpires: z.iso.datetime({ offset: true }).nullable().optional(),
      isEnabled: z.boolean(),
      dateLastUsed: z.iso.datetime({ offset: true }).nullable().optional(),
      isDeleted: z.boolean(),
      dateDeleted: z.iso.datetime({ offset: true }).nullable().optional(),
      isExpired: z.boolean(),
      publicKeyPreview: z.string()
   })
   .describe("Service Account Key Model");

export type ServiceAccountKeyModel = z.infer<
   typeof ServiceAccountKeyModelSchema
>;

export const RsaKeyPairModelSchema = z
   .object({
      publicKey: z.string(),
      privateKey: z.string(),
      keySize: z.number().int(),
      generatedAt: z.iso.datetime({ offset: true })
   })
   .describe("RSA Key Pair Model");

export type RsaKeyPairModel = z.infer<typeof RsaKeyPairModelSchema>;

// ============================================================================
// Service Account Request Models
// ============================================================================

export const CreateServiceAccountRequestSchema = z
   .object({
      serviceAccountId: z
         .email()
         .max(256)
         .describe(
            "The unique email address identifier for the service account"
         ),
      firstName: z
         .string()
         .max(100)
         .regex(/^[a-zA-ZÀ-ÿ][-'a-zA-ZÀ-ÿ ]{0,}$/)
         .describe("First name of the service account representative"),
      lastName: z
         .string()
         .max(100)
         .regex(/^[a-zA-ZÀ-ÿ][-'a-zA-ZÀ-ÿ ]{0,}$/)
         .nullable()
         .optional()
         .describe("Last name of the service account representative"),
      isEnabled: z.boolean().describe("Whether the service account is enabled")
   })
   .describe("Create Service Account Request");

export type CreateServiceAccountRequest = z.infer<
   typeof CreateServiceAccountRequestSchema
>;

export const CreateServiceAccountKeyRequestSchema = z
   .object({
      userId: z
         .guid()
         .describe("The user ID associated with the service account"),
      publicKey: z
         .string()
         .max(4096)
         .regex(
            /^-----BEGIN PUBLIC KEY-----[\s\S]+-----END PUBLIC KEY-----\s*$/
         )
         .describe("The RSA public key in PEM format"),
      keyName: z
         .string()
         .max(100)
         .nullable()
         .optional()
         .describe("Optional friendly name for the key"),
      dateExpires: z.iso.datetime({ offset: true }).nullable().optional(),
      isEnabled: z.boolean()
   })
   .describe("Create Service Account Key Request");

export type CreateServiceAccountKeyRequest = z.infer<
   typeof CreateServiceAccountKeyRequestSchema
>;

export const UpdateServiceAccountKeyRequestSchema = z
   .object({
      isEnabled: z.boolean()
   })
   .describe("Update Service Account Key Request");

export type UpdateServiceAccountKeyRequest = z.infer<
   typeof UpdateServiceAccountKeyRequestSchema
>;

export const UpdateServiceAccountStatusRequestSchema = z
   .object({
      isEnabled: z.boolean()
   })
   .describe("Update Service Account Status Request");

export type UpdateServiceAccountStatusRequest = z.infer<
   typeof UpdateServiceAccountStatusRequestSchema
>;

export const ServiceAccountAuthRequestSchema = z
   .object({
      token: z.string()
   })
   .describe("Service Account Auth Request");

export type ServiceAccountAuthRequest = z.infer<
   typeof ServiceAccountAuthRequestSchema
>;

export const GenerateServiceAccountTokenRequestSchema = z
   .object({
      expirationDays: z.number().int().min(1).max(3650)
   })
   .describe("Generate Service Account Token Request");

export type GenerateServiceAccountTokenRequest = z.infer<
   typeof GenerateServiceAccountTokenRequestSchema
>;

// ============================================================================
// Service Account Response Models
// ============================================================================

export const ServiceAccountTokenResponseSchema = z
   .object({
      token: z.string(),
      expiresAt: z.iso.datetime({ offset: true })
   })
   .describe("Service Account Token Response");

export type ServiceAccountTokenResponse = z.infer<
   typeof ServiceAccountTokenResponseSchema
>;

// ============================================================================
// Paginated Service Account Lists
// ============================================================================

export const PaginatedListOfServiceAccountModelSchema = z
   .object({
      items: z.array(z.lazy(() => ServiceAccountModelSchema)).default([]),
      totalCount: z.number().int(),
      pageIndex: z.number().int(),
      pageSize: z.number().int(),
      totalPages: z.number().int().optional()
   })
   .describe("Paginated List Of Service Account Model");

export type PaginatedListOfServiceAccountModel = z.infer<
   typeof PaginatedListOfServiceAccountModelSchema
>;

export const PaginatedListOfServiceAccountKeyModelSchema = z
   .object({
      items: z.array(z.lazy(() => ServiceAccountKeyModelSchema)).default([]),
      totalCount: z.number().int(),
      pageIndex: z.number().int(),
      pageSize: z.number().int(),
      totalPages: z.number().int().optional()
   })
   .describe("Paginated List Of Service Account Key Model");

export type PaginatedListOfServiceAccountKeyModel = z.infer<
   typeof PaginatedListOfServiceAccountKeyModelSchema
>;
