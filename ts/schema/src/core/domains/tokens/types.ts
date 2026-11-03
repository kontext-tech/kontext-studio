import { z } from "zod";

/**
 * Token Purpose enum
 */
export const TokenPurposeSchema = z
   .enum([
      "EmailUnsubscribe",
      "InvitationCode",
      "AccountRegister",
      "EmailVerification",
      "PasswordReset"
   ])
   .describe("Token Purpose enum");

export type TokenPurpose = z.infer<typeof TokenPurposeSchema>;
export const TokenPurpose = TokenPurposeSchema.enum;
