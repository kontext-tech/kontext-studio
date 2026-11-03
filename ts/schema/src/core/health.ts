import { z } from "zod";

// Health-related models for Kontext

export const HealthCheckResponseSchema = z
   .object({
      status: z.string().describe("Health status"),
      timestamp: z.iso
         .datetime({ offset: true })
         .describe("ISO 8601 datetime string with timezone"),
      version: z.string().describe("Application version"),
      error: z.string().optional().describe("Error message if unhealthy")
   })
   .describe("Health check response model");

export const PingResponseSchema = z
   .object({
      status: z.string().describe("Status message")
   })
   .describe("Simple ping response");

export const HealthCheckRequestSchema = z
   .object({})
   .describe("Health check request model - can be empty for simple checks");

export const PingRequestSchema = z
   .object({})
   .describe("Ping request model - can be empty for simple pings");

export type HealthCheckResponse = z.infer<typeof HealthCheckResponseSchema>;
export type PingResponse = z.infer<typeof PingResponseSchema>;
export type HealthCheckRequest = z.infer<typeof HealthCheckRequestSchema>;
export type PingRequest = z.infer<typeof PingRequestSchema>;
