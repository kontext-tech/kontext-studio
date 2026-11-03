/**
 * Core utility functions for the notebook system
 */

/**
 * Creates a unique ID for blocks
 */
export function createBlockId(): string {
   return crypto.randomUUID();
}
