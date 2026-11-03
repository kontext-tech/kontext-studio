/**
 * Identity Domain: Central Exports
 *
 * Re-exports all identity-related schemas, types, and constants.
 * This is the public API for the identity domain.
 */

// Shared types and enums
export * from "./types.js";

// User schemas and types
export {
   PaginatedListOfUserWithProjectRolesModelSchema,
   // Paginated lists
   PaginatedListOfUserWithRolesModelSchema,
   UpdateUserCredentialsRequestSchema,
   UpdateUserProfileRequestSchema,
   // Helper function
   UpdateUserRequestSchema,
   // User models
   UserDetailsWithEmailModelSchema,
   UserMetadataSchema,
   UserModelSchema,
   // User requests
   UserRegistrationRequestSchema,
   // Enums
   type PaginatedListOfUserWithProjectRolesModel,
   type PaginatedListOfUserWithRolesModel,
   type UpdateUserCredentialsRequest,
   type UpdateUserProfileRequest,
   type UpdateUserRequest,
   type UserDetailsWithEmailModel,
   type UserMetadata,
   type UserModel,
   type UserRegistrationRequest
} from "./users.js";

// Role schemas and types
export {
   // Permission models
   ApplicationPermissionModelSchema,
   ApplicationRoleClaimModelSchema,
   // Role requests
   CreateRoleRequestSchema,
   // Paginated lists
   PaginatedListOfRoleModelSchema,
   PermissionClaimModelSchema,
   RoleClaimAssignmentRequestSchema,
   RoleClaimModelSchema,
   RoleMetadataSchema,
   // Role models
   RoleModelSchema,
   UpdateRoleRequestSchema,
   UpdateUserProjectRolesRequestSchema,
   UserRoleAssignmentRequestSchema,
   UserWithProjectRolesModelSchema,
   UserWithRolesModelSchema,
   type ApplicationPermissionModel,
   type ApplicationRoleClaimModel,
   type CreateRoleRequest,
   type PaginatedListOfRoleModel,
   type PermissionClaimModel,
   type RoleClaimAssignmentRequest,
   type RoleClaimModel,
   type RoleMetadata,
   type RoleModel,
   type UpdateRoleRequest,
   type UpdateUserProjectRolesRequest,
   type UserRoleAssignmentRequest,
   type UserWithProjectRolesModel,
   type UserWithRolesModel
} from "./roles.js";

// Service account schemas and types
export {
   CreateServiceAccountKeyRequestSchema,
   // Service account requests
   CreateServiceAccountRequestSchema,
   GenerateServiceAccountTokenRequestSchema,
   PaginatedListOfServiceAccountKeyModelSchema,
   // Paginated lists
   PaginatedListOfServiceAccountModelSchema,
   RsaKeyPairModelSchema,
   ServiceAccountAuthRequestSchema,
   ServiceAccountKeyModelSchema,
   // Service account models
   ServiceAccountModelSchema,
   // Service account responses
   ServiceAccountTokenResponseSchema,
   UpdateServiceAccountKeyRequestSchema,
   UpdateServiceAccountStatusRequestSchema,
   type CreateServiceAccountKeyRequest,
   type CreateServiceAccountRequest,
   type GenerateServiceAccountTokenRequest,
   type PaginatedListOfServiceAccountKeyModel,
   type PaginatedListOfServiceAccountModel,
   type RsaKeyPairModel,
   type ServiceAccountAuthRequest,
   type ServiceAccountKeyModel,
   type ServiceAccountModel,
   type ServiceAccountTokenResponse,
   type UpdateServiceAccountKeyRequest,
   type UpdateServiceAccountStatusRequest
} from "./service-accounts.js";

// Authentication schemas and types
export {
   // Auth responses
   AccessTokenResponseSchema,
   // Admin models
   EmailConfirmationResultSchema,
   EnableTwoFactorRequestSchema,
   ForgotPasswordRequestSchema,
   // Auth requests
   LoginRequestSchema,
   RefreshRequestSchema,
   ResendConfirmationEmailRequestSchema,
   ResetPasswordRequestSchema,
   TwoFactorResponseSchema,
   type AccessTokenResponse,
   type EmailConfirmationResult,
   type EnableTwoFactorRequest,
   type ForgotPasswordRequest,
   type LoginRequest,
   type RefreshRequest,
   type ResendConfirmationEmailRequest,
   type ResetPasswordRequest,
   type TwoFactorResponse
} from "./auth.js";

// Setup schemas and types
export {
   SetupRequestSchema,
   SetupStatusResponseSchema,
   type SetupRequest,
   type SetupStatusResponse
} from "./setup.js";
