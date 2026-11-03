/**
 * Notebook schema validation utilities
 * Provides validation functions for blocks and documents
 */

import { z } from "zod";

// ============================================================================
// Validation Error Types
// ============================================================================

export interface NotebookValidationError {
   field: string;
   message: string;
   code?: string;
}

export interface NotebookValidationResult {
   valid: boolean;
   errors: NotebookValidationError[];
}

// ============================================================================
// Validation Utilities
// ============================================================================

/**
 * Convert Zod errors to our validation error format
 */
function convertZodErrors(zodErrors: z.ZodError): NotebookValidationError[] {
   return zodErrors.issues.map((error: z.core.$ZodIssue) => ({
      field: error.path.join("."),
      message: error.message,
      code: error.code
   }));
}

/**
 * Validate a block against its schema
 */
export function validateBlock(
   block: unknown,
   schema: z.ZodSchema
): NotebookValidationResult {
   try {
      schema.parse(block);
      return { valid: true, errors: [] };
   } catch (error) {
      if (error instanceof z.ZodError) {
         return {
            valid: false,
            errors: convertZodErrors(error)
         };
      }
      return {
         valid: false,
         errors: [
            { field: "", message: "Unknown validation error", code: "unknown" }
         ]
      };
   }
}

/**
 * Validate a notebook document
 */
export function validateDocument(
   document: unknown,
   schema: z.ZodSchema
): NotebookValidationResult {
   try {
      schema.parse(document);
      return { valid: true, errors: [] };
   } catch (error) {
      if (error instanceof z.ZodError) {
         return {
            valid: false,
            errors: convertZodErrors(error)
         };
      }
      return {
         valid: false,
         errors: [
            { field: "", message: "Unknown validation error", code: "unknown" }
         ]
      };
   }
}

/**
 * Get validation error messages as a formatted string
 */
export function getValidationErrorMessages(
   errors: NotebookValidationError[]
): string {
   return errors
      .map((error) =>
         error.field ? `${error.field}: ${error.message}` : error.message
      )
      .join("\n");
}

/**
 * Check if a value is valid according to a schema
 */
export function isValid(value: unknown, schema: z.ZodSchema): boolean {
   try {
      schema.parse(value);
      return true;
   } catch {
      return false;
   }
}
