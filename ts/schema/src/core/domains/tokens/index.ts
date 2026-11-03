import { z } from "zod";

import { BaseModelSchema } from "../base/index.js";
import { TokenPurposeSchema } from "./types.js";
export * from "./types.js";

/**
 * Core Domain: Tokens
 *
 * Source: backend/Kontext.Data/ViewModels/TokenViewModel.cs
 */

export const TokenModelSchema = BaseModelSchema.extend({
   code: z.string(),
   purpose: z.lazy(() => TokenPurposeSchema),
   expiresAt: z.iso.datetime({ offset: true }).nullable().optional(),
   isUsed: z.boolean(),
   dateCreated: z.iso.datetime({ offset: true })
}).describe("Token Model");

export type TokenModel = z.infer<typeof TokenModelSchema>;

export const ValidateTokenRequestSchema = z
   .object({
      purpose: z.lazy(() => TokenPurposeSchema),
      value: z.string(),
      code: z.string()
   })
   .describe("Validate Token Request");

export type ValidateTokenRequest = z.infer<typeof ValidateTokenRequestSchema>;

export const CreateTokenRequestSchema = z
   .object({
      purpose: z.lazy(() => TokenPurposeSchema),
      value: z.string(),
      code: z.string(),
      expiresAt: z.iso.datetime({ offset: true }).nullable().optional()
   })
   .describe("Create Token Request");

export type CreateTokenRequest = z.infer<typeof CreateTokenRequestSchema>;
