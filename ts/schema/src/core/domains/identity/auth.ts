/**
 * Identity Domain: Authentication Models
 *
 * Zod-first schema definitions for authentication and authorization.
 */

import { z } from "zod";

// ============================================================================
// Authentication Request Models
// ============================================================================

export const LoginRequestSchema = z
   .object({
      email: z.email(),
      password: z.string().min(1, "Password is required"),
      twoFactorCode: z.string().nullable().optional(),
      twoFactorRecoveryCode: z.string().nullable().optional()
   })
   .describe("Login Request");

export type LoginRequest = z.infer<typeof LoginRequestSchema>;

export const RefreshRequestSchema = z
   .object({
      refreshToken: z.string()
   })
   .describe("Refresh Request");

export type RefreshRequest = z.infer<typeof RefreshRequestSchema>;

export const ForgotPasswordRequestSchema = z
   .object({
      email: z.email()
   })
   .describe("Forgot Password Request");

export type ForgotPasswordRequest = z.infer<typeof ForgotPasswordRequestSchema>;

export const ResetPasswordRequestSchema = z
   .object({
      email: z.email(),
      resetCode: z.string(),
      newPassword: z.string()
   })
   .describe("Reset Password Request");

export type ResetPasswordRequest = z.infer<typeof ResetPasswordRequestSchema>;

export const ResendConfirmationEmailRequestSchema = z
   .object({
      email: z.email()
   })
   .describe("Resend Confirmation Email Request");

export type ResendConfirmationEmailRequest = z.infer<
   typeof ResendConfirmationEmailRequestSchema
>;

export const EnableTwoFactorRequestSchema = z
   .object({
      enable: z.boolean(),
      twoFactorCode: z.string().nullable().optional()
   })
   .describe("Enable Two Factor Request");

export type EnableTwoFactorRequest = z.infer<
   typeof EnableTwoFactorRequestSchema
>;

// ============================================================================
// Authentication Response Models
// ============================================================================

export const AccessTokenResponseSchema = z
   .object({
      tokenType: z.string().nullable().optional(),
      accessToken: z.string(),
      expiresIn: z.number().int(),
      refreshToken: z.string()
   })
   .describe("Access Token Response");

export type AccessTokenResponse = z.infer<typeof AccessTokenResponseSchema>;

export const TwoFactorResponseSchema = z
   .object({
      sharedKey: z.string(),
      recoveryCodesLeft: z.number().int(),
      recoveryCodes: z.array(z.string()).nullable().optional(),
      isTwoFactorEnabled: z.boolean()
   })
   .describe("Two Factor Response");

export type TwoFactorResponse = z.infer<typeof TwoFactorResponseSchema>;

export const EmailConfirmationResultSchema = z
   .object({
      success: z.boolean(),
      errorMessage: z.string().nullable().optional(),
      redirectUrl: z.string().nullable().optional()
   })
   .describe("Email Confirmation Result");

export type EmailConfirmationResult = z.infer<
   typeof EmailConfirmationResultSchema
>;
