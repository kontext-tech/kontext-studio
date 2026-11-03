// Core API schemas - Zod-first domain contracts
//
// All schemas are hand-authored in ./domains/* (single source of truth)

// Shared core contracts
export * from "./data";
export * from "./health";
export * from "./artifact-provenance";

// Export all domain schemas
export * from "./domains/index.js";
