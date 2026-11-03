/**
 * Identity Domain: Role Models
 *
 * Zod-first schema definitions for role-based access control.
 */

import { z } from "zod";
import { UserDetailsModelSchema, UserNavModelSchema } from "./types.js";

// ============================================================================
// Permission & Claim Models
// ============================================================================

export const ApplicationPermissionModelSchema = z
   .object({
      name: z.string(),
      value: z.string(),
      groupName: z.string().nullable().optional(),
      description: z.string().nullable().optional(),
      isSelected: z.boolean()
   })
   .describe("Application Permission Model");

export type ApplicationPermissionModel = z.infer<
   typeof ApplicationPermissionModelSchema
>;

export const ApplicationRoleClaimModelSchema = z
   .object({
      claimType: z.string(),
      claimValue: z.string()
   })
   .describe("Application Role Claim Model");

export type ApplicationRoleClaimModel = z.infer<
   typeof ApplicationRoleClaimModelSchema
>;

export const PermissionClaimModelSchema = z
   .object({
      name: z.string(),
      value: z.string(),
      groupName: z.string().nullable().optional(),
      description: z.string().nullable().optional()
   })
   .describe("Permission Claim Model");

export type PermissionClaimModel = z.infer<typeof PermissionClaimModelSchema>;

export const RoleClaimModelSchema = z
   .object({
      claimType: z.string(),
      claimValue: z.string(),
      name: z.string().nullable().optional(),
      groupName: z.string().nullable().optional(),
      description: z.string().nullable().optional()
   })
   .describe("Role Claim Model");

export type RoleClaimModel = z.infer<typeof RoleClaimModelSchema>;

// ============================================================================
// Role Models
// ============================================================================

export const RoleModelSchema = z
   .object({
      id: z.guid(),
      name: z.string().min(2).max(200),
      description: z.string().max(500).nullable().optional(),
      isSystemRole: z.boolean(),
      projectId: z.guid().nullable().optional(),
      isProjectScopedRole: z.boolean(),
      claims: z
         .array(z.lazy(() => ApplicationRoleClaimModelSchema))
         .default([]),
      isSelected: z.boolean()
   })
   .describe("Role Model");

export type RoleModel = z.infer<typeof RoleModelSchema>;

// ============================================================================
// User + Role Combined Models
// ============================================================================

export const UserWithRolesModelSchema = UserNavModelSchema.extend({
   roles: z.array(z.string()).default([]),
   permissionClaims: z.array(z.string()).default([]),
   projectRoles: z.record(z.string(), z.array(z.string())).default({}),
   dateRegister: z.iso.datetime({ offset: true }).nullable().optional()
}).describe("User With Roles Model");

export type UserWithRolesModel = z.infer<typeof UserWithRolesModelSchema>;

export const UserWithProjectRolesModelSchema = UserDetailsModelSchema.extend({
   projectRoles: z.array(z.string()).default([])
}).describe("User With Project Roles Model");

export type UserWithProjectRolesModel = z.infer<
   typeof UserWithProjectRolesModelSchema
>;

// ============================================================================
// Role Request Models
// ============================================================================

export const CreateRoleRequestSchema = z
   .object({
      id: z.guid(),
      name: z.string().min(2).max(200),
      description: z.string().max(500).nullable().optional(),
      permissions: z
         .array(z.lazy(() => ApplicationPermissionModelSchema))
         .nullable()
         .optional()
   })
   .describe("Create Role Request");

export type CreateRoleRequest = z.infer<typeof CreateRoleRequestSchema>;

export const UpdateRoleRequestSchema = z
   .object({
      name: z.string().min(2).max(200),
      description: z.string().max(500).nullable().optional(),
      permissions: z
         .array(z.lazy(() => ApplicationRoleClaimModelSchema))
         .nullable()
         .optional()
   })
   .describe("Update Role Request");

export type UpdateRoleRequest = z.infer<typeof UpdateRoleRequestSchema>;

export const UserRoleAssignmentRequestSchema = z
   .object({
      userId: z.guid(),
      roleNames: z.array(z.string())
   })
   .describe("User Role Assignment Request");

export type UserRoleAssignmentRequest = z.infer<
   typeof UserRoleAssignmentRequestSchema
>;

export const RoleClaimAssignmentRequestSchema = z
   .object({
      roleId: z.guid(),
      claimValues: z.array(z.string())
   })
   .describe("Role Claim Assignment Request");

export type RoleClaimAssignmentRequest = z.infer<
   typeof RoleClaimAssignmentRequestSchema
>;

export const UpdateUserProjectRolesRequestSchema = z
   .object({
      userId: z.guid(),
      roles: z.array(z.string()).nullable().optional()
   })
   .describe("Update User Project Roles Request");

export type UpdateUserProjectRolesRequest = z.infer<
   typeof UpdateUserProjectRolesRequestSchema
>;

/**
 * C#-only ViewModel (currently not exposed in Core OpenAPI)
 * Source: backend/Kontext.Data/ViewModels/Identity/RoleMetadata.cs
 */
export const RoleMetadataSchema = z
   .object({
      id: z.guid(),
      name: z.string().max(200),
      description: z.string().nullable().optional(),
      permissions: z
         .array(z.lazy(() => ApplicationPermissionModelSchema))
         .nullable()
         .optional(),
      isSelected: z.boolean()
   })
   .describe("Role Metadata");

export type RoleMetadata = z.infer<typeof RoleMetadataSchema>;

// ============================================================================
// Paginated Role Lists
// ============================================================================

export const PaginatedListOfRoleModelSchema = z
   .object({
      items: z.array(z.lazy(() => RoleModelSchema)).default([]),
      totalCount: z.number().int(),
      pageIndex: z.number().int(),
      pageSize: z.number().int(),
      totalPages: z.number().int().optional()
   })
   .describe("Paginated List Of Role Model");

export type PaginatedListOfRoleModel = z.infer<
   typeof PaginatedListOfRoleModelSchema
>;
